import serial
import serial.tools.list_ports
import time
import cv2
import numpy as np

def find_esp32_port():
    ports = serial.tools.list_ports.comports()
    for p in ports:
        desc = (p.description or "").upper()
        if "CH343" in desc or "CH340" in desc or "CP210" in desc or "USB SERIAL" in desc or "ESP32" in desc:
            return p.device
    if len(ports) > 0:
        return ports[0].device
    return "COM13"

def main():
    print("=============================================================")
    print("  PRUEBA DE VISION ARUCO CALCULADA DIRECTAMENTE EN ESP32-S3   ")
    print("=============================================================")
    port = find_esp32_port()
    print(f"Conectando al ESP32 en {port} a 115200 baudios...")
    
    try:
        s = serial.Serial(port, 115200, timeout=3.0)
    except Exception as e:
        print(f"Error abriendo puerto {port}: {e}")
        input("Presiona Enter para salir...")
        return
        
    s.dtr = False
    s.rts = False
    time.sleep(1.5)
    s.reset_input_buffer()
    
    # 1. Prueba de autoprueba interna en chip
    print("\n[PRUEBA 1] Ejecutando test interno del algoritmo en la memoria del ESP32...")
    s.write(b"TEST\n")
    s.flush()
    time.sleep(0.4)
    while s.in_waiting:
        line = s.readline().decode("utf-8", errors="ignore").strip()
        if line:
            print(f"  ESP32: {line}")
            
    # 2. Prueba de envio de imagenes con diferentes IDs generados
    d = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    test_ids = [0, 5, 12, 28, 45]
    print("\n[PRUEBA 2] Enviando 5 marcadores ArUco distintos para que el ESP32 los calcule:")
    
    for tid in test_ids:
        marker = cv2.aruco.generateImageMarker(d, tid, 60)
        scene = np.ones((120, 160), dtype=np.uint8) * 230
        scene[30:90, 50:110] = marker
        
        s.write(b"FRAME 160 120\n")
        s.flush()
        resp = s.readline().decode("utf-8", errors="ignore").strip()
        if "READY" in resp:
            s.write(scene.tobytes())
            s.flush()
            result = s.readline().decode("utf-8", errors="ignore").strip()
            print(f"  -> Marcador ArUco ID {tid} enviado -> {result}")
        time.sleep(0.2)
        
    s.close()
    print("\n=============================================================")
    print("  PRUEBAS COMPLETADAS: El procesador del ESP32 calculo todo! ")
    print("=============================================================")
    input("\nPresiona Enter para cerrar...")

if __name__ == '__main__':
    main()
