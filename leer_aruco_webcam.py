import cv2
import serial
import serial.tools.list_ports
import time
import numpy as np

def find_esp32_port():
    ports = serial.tools.list_ports.comports()
    for p in ports:
        if "CH343" in p.description or "CH340" in p.description or "CP210" in p.description or "USB Serial" in p.description or "ESP32" in p.description:
            return p.device
    if len(ports) > 0:
        return ports[0].device
    return "COM13"

def main():
    port_name = find_esp32_port()
    print(f"Conectando al ESP32-S3 en {port_name} a 2,000,000 baudios...")
    
    try:
        ser = serial.Serial(port_name, 2000000, timeout=0.1)
    except Exception as e:
        print(f"Error al abrir el puerto {port_name}: {e}")
        return

    time.sleep(0.3)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    print("Abriendo camara de la computadora...")
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("No se pudo acceder a la camara web de la computadora.")
        ser.close()
        return

    print("Camara iniciada correctamente.")
    print("Muestra un marcador ArUco 4x4 (en papel o celular) frente a la camara.")
    print("Presiona la tecla 'q' en la ventana para salir.\n")

    w, h = 80, 60
    header_w = 0x80 | ((w >> 8) & 0x7F)
    sof = bytes([0xFF, 0xAA, 0x55, 0xEE, header_w, w & 0xFF, (h >> 8) & 0xFF, h & 0xFF])

    last_detection_text = "Esperando marcador..."
    last_detection_time = 0
    fps_time = time.time()
    frame_count = 0
    fps_display = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        now = time.time()
        if now - fps_time >= 1.0:
            fps_display = frame_count / (now - fps_time)
            frame_count = 0
            fps_time = now

        # Redimensionar a escala de grises 80x60 para el microcontrolador
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (w, h), interpolation=cv2.INTER_AREA)

        # Empaquetado a 4 bits (nibble) para transmision ultrarrapida
        packet = bytearray(sof)
        for y in range(h):
            packet.append(0xA5)
            packet.append(y)
            row = small[y]
            # Empaquetar de dos en dos pixeles
            p0 = (row[0::2] >> 4) & 0x0F
            p1 = (row[1::2] >> 4) & 0x0F
            nibbles = (p0 << 4) | p1
            packet.extend(nibbles)

        try:
            ser.write(packet)
            resp = ser.read(20)

            if len(resp) == 20 and resp[:4] == bytes([0xEE, 0x55, 0xAA, 0xFF]):
                status = resp[4]
                det_id = resp[5]
                cpu_ms = resp[6]

                if status == 1 and det_id < 50:
                    last_detection_text = f"ARUCO ID {det_id} DETECTADO (CPU ESP32: {cpu_ms} ms)"
                    last_detection_time = time.time()
                    print(f"[ESP32-S3] Marcador ArUco ID {det_id} identificado en {cpu_ms} ms!")

                    # Coordenadas de las 4 esquinas escaladas al tamano del frame original
                    orig_h, orig_w = frame.shape[:2]
                    corners = []
                    for i in range(4):
                        cx = int(resp[10 + i * 2] * (orig_w / float(w)))
                        cy = int(resp[11 + i * 2] * (orig_h / float(h)))
                        corners.append((cx, cy))

                    pts = np.array(corners, np.int32)
                    pts = pts.reshape((-1, 1, 2))
                    cv2.polylines(frame, [pts], True, (0, 255, 0), 3)

                    # Dibujar etiqueta
                    min_x = min(c[0] for c in corners)
                    min_y = min(c[1] for c in corners)
                    cv2.putText(frame, f"ID {det_id}", (min_x, max(30, min_y - 10)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        except Exception as err:
            pass

        # Mostrar estado en la imagen
        is_active = (time.time() - last_detection_time < 3.0)
        color_banner = (0, 200, 0) if is_active else (50, 50, 50)
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 45), (15, 15, 15), -1)
        cv2.putText(frame, last_detection_text if is_active else "Buscando ArUco 4x4...",
                    (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color_banner, 2)
        cv2.putText(frame, f"{fps_display:.1f} FPS", (frame.shape[1] - 110, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

        cv2.imshow("ESP32-S3 Lector de ArUco por Cable", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    ser.close()
    print("Programa finalizado.")

if __name__ == '__main__':
    main()
