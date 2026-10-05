import cv2
import serial
import serial.tools.list_ports
import time
import threading
import numpy as np

# =========================================================================
# CONFIGURACION DE ENLACES
# =========================================================================
IP_CAMERA_URLS = [
    "http://admin:1234@192.168.100.113:8081/video",
    "http://admin:1234@192.168.100.113:8081/",
    "http://admin:1234@192.168.100.113:8081/live",
    "http://192.168.100.113:8081/video",
    "http://192.168.100.113:8081/live"
]

def find_esp32_port():
    ports = serial.tools.list_ports.comports()
    for p in ports:
        desc = (p.description or "").upper()
        if "CH343" in desc or "CH340" in desc or "CP210" in desc or "USB SERIAL" in desc or "ESP32" in desc:
            return p.device
    if len(ports) > 0:
        return ports[0].device
    return "COM13"

# =========================================================================
# COMUNICACION SERIE CON ESP32-S3
# =========================================================================
class Esp32Bridge:
    def __init__(self, port_name, baud=115200):
        self.port_name = port_name
        self.baud = baud
        self.ser = None
        self.is_connected = False
        self.last_status_msg = "Conectando al ESP32-S3..."
        self.last_reply = ""
        self.lock = threading.Lock()
        self.running = True
        self.connect()

        self.rx_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.rx_thread.start()

    def connect(self):
        try:
            self.ser = serial.Serial(self.port_name, self.baud, timeout=0.2)
            time.sleep(0.3)
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            self.is_connected = True
            self.last_status_msg = f"ESP32 Conectado en {self.port_name}"
            print(f"[CONEXION] ESP32-S3 conectado en {self.port_name}")
        except Exception as e:
            self.is_connected = False
            self.last_status_msg = f"ESP32 no detectado en {self.port_name} (Modo Camara)"
            print(f"[AVISO] No se pudo conectar a {self.port_name}: {e}")

    def send_cmd(self, cmd_str):
        if not self.is_connected or not self.ser:
            return
        with self.lock:
            try:
                line = (cmd_str.strip() + "\n").encode("ascii")
                self.ser.write(line)
                self.ser.flush()
            except Exception as e:
                self.is_connected = False
                print(f"[ERROR TX] Error enviando al ESP32: {e}")

    def _read_loop(self):
        while self.running:
            if self.is_connected and self.ser:
                try:
                    if self.ser.in_waiting:
                        line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                        if line:
                            self.last_reply = line
                            print(f"{line}")
                except Exception:
                    pass
            time.sleep(0.02)

    def close(self):
        self.running = False
        if self.ser and self.is_connected:
            try:
                self.ser.close()
            except Exception:
                pass

# =========================================================================
# RECEPTOR DE STREAM DE VIDEO EN TIEMPO REAL (IP + WEBCAM LOCAL)
# =========================================================================
class CameraStream:
    def __init__(self, ip_urls, fallback_index=0):
        self.ip_urls = ip_urls
        self.fallback_index = fallback_index
        self.current_mode = "IP"  # "IP" o "WEBCAM"
        self.cap = None
        self.frame = None
        self.ret = False
        self.lock = threading.Lock()
        self.running = True
        self.is_connected = False
        self.source_desc = "Conectando..."
        self._open_stream()
        self.thread = threading.Thread(target=self._update_loop, daemon=True)
        self.thread.start()

    def _open_stream(self):
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

        if self.current_mode == "IP":
            for url in self.ip_urls:
                try:
                    display_url = url.split("@")[-1] if "@" in url else url
                    print(f"[CAMARA] Probando stream IP: {display_url} ...")
                    c = cv2.VideoCapture(url)
                    if c.isOpened():
                        ok, f = c.read()
                        if ok and f is not None:
                            self.cap = c
                            self.is_connected = True
                            self.source_desc = f"IP: {display_url}"
                            print(f"[CAMARA] Conectado exitosamente a: {self.source_desc}")
                            return
                        c.release()
                except Exception:
                    pass
            print("[CAMARA] No se pudo conectar a la camara IP. Cambiando a webcam local...")
            self.current_mode = "WEBCAM"

        # Intento con webcam local USB
        try:
            print(f"[CAMARA] Abriendo webcam local indice {self.fallback_index}...")
            c = cv2.VideoCapture(self.fallback_index, cv2.CAP_DSHOW)
            if not c.isOpened():
                c = cv2.VideoCapture(self.fallback_index)
            if c.isOpened():
                self.cap = c
                self.is_connected = True
                self.source_desc = f"Webcam Local ({self.fallback_index})"
                print(f"[CAMARA] Conectado a {self.source_desc}")
                return
        except Exception as e:
            print(f"[CAMARA] Error en webcam local: {e}")

        self.is_connected = False
        self.source_desc = "Sin conexion de camara"

    def switch_source(self):
        with self.lock:
            if self.current_mode == "IP":
                self.current_mode = "WEBCAM"
            else:
                self.current_mode = "IP"
            print(f"\n[CAMARA] Cambiando fuente seleccionada a modo {self.current_mode}...")
            self._open_stream()

    def _update_loop(self):
        consecutive_errors = 0
        while self.running:
            if self.cap and self.cap.isOpened():
                try:
                    ok, f = self.cap.read()
                    if ok and f is not None:
                        consecutive_errors = 0
                        self.is_connected = True
                        with self.lock:
                            self.ret = True
                            self.frame = f
                    else:
                        consecutive_errors += 1
                        time.sleep(0.02)
                except Exception:
                    consecutive_errors += 1
                    time.sleep(0.04)

                if consecutive_errors > 35:
                    self.is_connected = False
                    print("[CAMARA] Perdida de paquetes en el video. Reintentando...")
                    self._open_stream()
                    consecutive_errors = 0
            else:
                time.sleep(1.0)
                if self.running and not self.is_connected:
                    self._open_stream()

    def read(self):
        with self.lock:
            if self.frame is not None:
                return self.ret, self.frame.copy()
            return False, None

    def release(self):
        self.running = False
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass

# =========================================================================
# MODULOS DE DETECCION DE VISION ARTIFICIAL
# =========================================================================

# 1. Detector ArUco 4x4
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
aruco_params = cv2.aruco.DetectorParameters()
aruco_params.adaptiveThreshWinSizeMin = 3
aruco_params.adaptiveThreshWinSizeMax = 35
aruco_params.adaptiveThreshWinSizeStep = 4
aruco_params.minMarkerPerimeterRate = 0.05
aruco_params.maxMarkerPerimeterRate = 4.0
aruco_detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)

def process_aruco(frame):
    h, w = frame.shape[:2]
    corners, ids, _ = aruco_detector.detectMarkers(frame)
    if ids is None or len(ids) == 0:
        # Respaldo en modo espejo por si la camara invierte el eje optico
        flipped = cv2.flip(frame, 1)
        corners_f, ids_f, _ = aruco_detector.detectMarkers(flipped)
        if ids_f is not None and len(ids_f) > 0:
            ids = ids_f
            corners = []
            for c_arr in corners_f:
                reproj = c_arr.copy()
                reproj[:, :, 0] = w - 1 - reproj[:, :, 0]
                corners.append(reproj)

    detections = []
    if ids is not None and len(ids) > 0:
        for i in range(len(ids)):
            marker_id = int(ids[i].flatten()[0])
            c = corners[i].reshape((4, 2)).astype(int)
            detections.append((marker_id, c))
    return detections

# 2. Detector de los 4 Colores del Reglamento Candidates 2026
COLOR_RANGES = {
    "CELESTE (Adelante)": {
        "lower": np.array([82, 70, 100]),
        "upper": np.array([105, 255, 255]),
        "bgr": (230, 225, 92),
        "cmd": "CELESTE"
    },
    "AMARILLO (Derecha)": {
        "lower": np.array([22, 100, 120]),
        "upper": np.array([38, 255, 255]),
        "bgr": (89, 222, 255),
        "cmd": "AMARILLO"
    },
    "NARANJA (Atras)": {
        "lower": np.array([7, 120, 130]),
        "upper": np.array([21, 255, 255]),
        "bgr": (77, 145, 255),
        "cmd": "NARANJA"
    },
    "ROSA (Izquierda)": {
        "lower": np.array([145, 70, 120]),
        "upper": np.array([175, 255, 255]),
        "bgr": (196, 102, 255),
        "cmd": "ROSA"
    }
}

def process_colors(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    h, w = frame.shape[:2]
    min_area = (w * h) * 0.015  # Minimo 1.5% del area para evitar falsos positivos
    detections = []

    for name, conf in COLOR_RANGES.items():
        mask = cv2.inRange(hsv, conf["lower"], conf["upper"])
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > min_area:
                x, y, bw, bh = cv2.boundingRect(cnt)
                detections.append({
                    "name": name,
                    "box": (x, y, bw, bh),
                    "color": conf["bgr"],
                    "cmd": conf["cmd"],
                    "area": area
                })

    detections.sort(key=lambda d: d["area"], reverse=True)
    return detections[:2]

# 3. Detector de Linea Blanca en Fondo Verde
def process_white_line_on_green(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    h, w = frame.shape[:2]

    # Mascara para suelo verde de la pista
    green_mask = cv2.inRange(hsv, np.array([35, 40, 30]), np.array([88, 255, 255]))

    # Mascara para linea blanca (saturacion baja, brillo medio-alto)
    white_mask = cv2.inRange(hsv, np.array([0, 0, 155]), np.array([180, 80, 255]))

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    green_dilated = cv2.dilate(green_mask, kernel, iterations=2)

    has_green = (cv2.countNonZero(green_mask) > (w * h * 0.04))
    if has_green:
        line_mask = cv2.bitwise_and(white_mask, green_dilated)
    else:
        line_mask = white_mask

    line_mask = cv2.morphologyEx(line_mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
    line_mask = cv2.morphologyEx(line_mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)))

    contours, _ = cv2.findContours(line_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_line_area = (w * h) * 0.007

    best_line = None
    max_area = 0

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > min_line_area:
            rect = cv2.minAreaRect(cnt)
            (cx, cy), (rw, rh), angle = rect
            aspect = max(rw, rh) / max(1.0, min(rw, rh))
            if aspect >= 1.4 or area > (w * h * 0.025):
                if area > max_area:
                    max_area = area
                    offset_x = (cx - (w / 2.0)) / (w / 2.0)
                    box = cv2.boxPoints(rect).astype(int)
                    best_line = {
                        "center": (int(cx), int(cy)),
                        "box": box,
                        "offset_x": offset_x,
                        "area": area
                    }

    return best_line

# =========================================================================
# BOTONES INTERACTIVOS EN PANTALLA
# =========================================================================
buttons = [
    {"id": "aruco", "label": "1. ArUco 4x4", "active": True, "rect": (10, 10, 140, 34)},
    {"id": "colors", "label": "2. 4 Colores", "active": True, "rect": (160, 10, 140, 34)},
    {"id": "line", "label": "3. Linea Verde", "active": True, "rect": (310, 10, 145, 34)},
    {"id": "mirror", "label": "M. Espejo", "active": False, "rect": (465, 10, 120, 34)},
    {"id": "source", "label": "C. Cam: IP", "active": True, "rect": (595, 10, 150, 34)}
]

def update_buttons_layout(w):
    num_btns = len(buttons)
    pad = 8
    btn_w = max(105, (w - (pad * (num_btns + 1))) // num_btns)
    btn_h = 34
    cur_x = pad
    for b in buttons:
        b["rect"] = (cur_x, 10, btn_w, btn_h)
        cur_x += btn_w + pad

cam_global_ref = None

def on_mouse_click(event, x, y, flags, param):
    global cam_global_ref
    if event == cv2.EVENT_LBUTTONDOWN:
        for btn in buttons:
            bx, by, bw, bh = btn["rect"]
            if bx <= x <= bx + bw and by <= y <= by + bh:
                if btn["id"] == "source":
                    if cam_global_ref:
                        cam_global_ref.switch_source()
                else:
                    btn["active"] = not btn["active"]
                    print(f"[SELECTOR] {btn['label']} -> {'ACTIVADO' if btn['active'] else 'DESACTIVADO'}")
                break

# =========================================================================
# BUCLE PRINCIPAL DE EJECUCION
# =========================================================================
def main():
    global cam_global_ref

    print("=======================================================")
    print("  DETECTOR MULTI-MODO ROBORREGOS CANDIDATES 2026       ")
    print("=======================================================")
    print("Fuente de Video Principal: Stream IP (http://192.168.100.113:8081)")
    print("Respaldo: Camara Web USB Local\n")
    print("Controles en la ventana:")
    print("-> Clic directo en los botones superiores para activar o desactivar.")
    print("-> Teclado:")
    print("   [1] ArUco 4x4")
    print("   [2] 4 Colores del Reglamento")
    print("   [3] Linea Blanca en Fondo Verde")
    print("   [M] Modo Espejo (Invertir horizontal)")
    print("   [C] Alternar entre Camara IP y Camara USB")
    print("   [Q o ESC] Salir del programa\n")

    port = find_esp32_port()
    esp = Esp32Bridge(port)

    cam = CameraStream(IP_CAMERA_URLS, fallback_index=0)
    cam_global_ref = cam

    win_name = "RoBorregos Candidates 2026 - Detector Multi-Modo (ESP32-S3)"
    cv2.namedWindow(win_name, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(win_name, on_mouse_click)

    last_tx_time = {"aruco": 0, "color": 0, "line": 0}
    last_tx_val = {"aruco": -1, "color": "", "line": 0.0}

    # Esperar el primer frame
    print("[INICIO] Conectando al feed de video...")
    for _ in range(50):
        ret, frame = cam.read()
        if ret and frame is not None:
            break
        time.sleep(0.1)

    while True:
        ret, frame = cam.read()
        if not ret or frame is None:
            # Mostrar cuadro de espera si se corta la conexion
            placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(placeholder, "Conectando al stream de video...", (100, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 200, 255), 2)
            cv2.imshow(win_name, placeholder)
            if (cv2.waitKey(100) & 0xFF) in (ord('q'), 27):
                break
            continue

        h, w = frame.shape[:2]
        update_buttons_layout(w)

        # Actualizar etiqueta del boton de fuente
        if cam.current_mode == "IP":
            buttons[4]["label"] = "C. Cam: IP"
            buttons[4]["active"] = cam.is_connected
        else:
            buttons[4]["label"] = "C. Cam: USB"
            buttons[4]["active"] = cam.is_connected

        # Estado de los modos
        mode_aruco = buttons[0]["active"]
        mode_colors = buttons[1]["active"]
        mode_line = buttons[2]["active"]
        mode_mirror = buttons[3]["active"]

        if mode_mirror:
            frame = cv2.flip(frame, 1)

        now = time.time()
        active_reports = []

        # ----------------------------------------------------
        # 1. DETECCION DE ARUCO 4X4
        # ----------------------------------------------------
        if mode_aruco:
            aruco_results = process_aruco(frame)
            for marker_id, c in aruco_results:
                cv2.polylines(frame, [c], True, (0, 255, 0), 4)
                cx = int(c[:, 0].mean())
                cy = int(c[:, 1].mean())
                cv2.circle(frame, (cx, cy), 6, (0, 255, 0), -1)

                tag = f"ARUCO ID {marker_id}"
                (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.85, 2)
                tag_x = max(10, min(w - tw - 10, cx - tw // 2))
                tag_y = max(th + 60, cy - 20)

                cv2.rectangle(frame, (tag_x - 5, tag_y - th - 5), (tag_x + tw + 5, tag_y + 5), (0, 0, 0), -1)
                cv2.rectangle(frame, (tag_x - 5, tag_y - th - 5), (tag_x + tw + 5, tag_y + 5), (0, 255, 0), 2)
                cv2.putText(frame, tag, (tag_x, tag_y), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 255, 0), 2)

                active_reports.append(f"ArUco ID {marker_id}")

                if marker_id != last_tx_val["aruco"] or (now - last_tx_time["aruco"] > 0.6):
                    last_tx_val["aruco"] = marker_id
                    last_tx_time["aruco"] = now
                    esp.send_cmd(f"ARUCO {marker_id}")

        # ----------------------------------------------------
        # 2. DETECCION DE LOS 4 COLORES
        # ----------------------------------------------------
        if mode_colors:
            color_results = process_colors(frame)
            for c_info in color_results:
                bx, by, bw, bh = c_info["box"]
                bgr = c_info["color"]
                c_name = c_info["name"]

                cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), bgr, 3)
                label = f"COLOR: {c_name}"
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)
                lbl_y = max(th + 60, by - 10)
                cv2.rectangle(frame, (bx, lbl_y - th - 5), (bx + tw + 8, lbl_y + 5), (10, 10, 10), -1)
                cv2.rectangle(frame, (bx, lbl_y - th - 5), (bx + tw + 8, lbl_y + 5), bgr, 2)
                cv2.putText(frame, label, (bx + 4, lbl_y), cv2.FONT_HERSHEY_SIMPLEX, 0.75, bgr, 2)

                active_reports.append(c_name.split()[0])

                if c_info["cmd"] != last_tx_val["color"] or (now - last_tx_time["color"] > 0.8):
                    last_tx_val["color"] = c_info["cmd"]
                    last_tx_time["color"] = now
                    esp.send_cmd(f"COLOR {c_info['cmd']}")

        # ----------------------------------------------------
        # 3. DETECCION DE LINEA EN FONDO VERDE
        # ----------------------------------------------------
        if mode_line:
            line_res = process_white_line_on_green(frame)
            if line_res:
                box = line_res["box"]
                cx, cy = line_res["center"]
                off = line_res["offset_x"]

                cv2.drawContours(frame, [box], 0, (255, 255, 0), 3)
                cv2.circle(frame, (cx, cy), 7, (0, 255, 255), -1)

                cv2.line(frame, (w // 2, h - 50), (cx, cy), (0, 255, 255), 2)
                cv2.circle(frame, (w // 2, h - 50), 5, (0, 180, 255), -1)

                dir_text = "CENTRO"
                if off < -0.15:
                    dir_text = f"IZQUIERDA ({off:.2f})"
                elif off > 0.15:
                    dir_text = f"DERECHA (+{off:.2f})"

                tag = f"LINEA: {dir_text}"
                (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)
                cv2.rectangle(frame, (cx - tw // 2 - 6, cy - 25 - th), (cx + tw // 2 + 6, cy - 15), (0, 0, 0), -1)
                cv2.putText(frame, tag, (cx - tw // 2, cy - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 255), 2)

                active_reports.append(f"Linea {dir_text}")

                if abs(off - last_tx_val["line"]) > 0.08 or (now - last_tx_time["line"] > 0.5):
                    last_tx_val["line"] = off
                    last_tx_time["line"] = now
                    esp.send_cmd(f"LINE {off:.2f}")

        # ----------------------------------------------------
        # DIBUJAR BOTONES INTERACTIVOS EN LA PARTE SUPERIOR
        # ----------------------------------------------------
        cv2.rectangle(frame, (0, 0), (w, 54), (18, 22, 30), -1)
        cv2.line(frame, (0, 54), (w, 54), (45, 55, 75), 1)

        for btn in buttons:
            bx, by, bw, bh = btn["rect"]
            is_act = btn["active"]
            bg_col = (42, 140, 32) if is_act else (40, 46, 58)
            border_col = (72, 220, 60) if is_act else (75, 85, 105)
            text_col = (255, 255, 255) if is_act else (160, 170, 185)

            cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), bg_col, -1)
            cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), border_col, 2)

            check = "[ON]" if is_act else "[OFF]"
            if btn["id"] == "source":
                label = btn["label"]
            else:
                label = f"{check} {btn['label']}"
            cv2.putText(frame, label, (bx + 8, by + 23), cv2.FONT_HERSHEY_SIMPLEX, 0.46, text_col, 1)

        # ----------------------------------------------------
        # BARRA INFERIOR DE ESTADO Y TELEMETRIA
        # ----------------------------------------------------
        cv2.rectangle(frame, (0, h - 42), (w, h), (14, 17, 24), -1)
        cv2.line(frame, (0, h - 42), (w, h - 42), (38, 48, 65), 1)

        # Mensaje de deteccion
        if active_reports:
            summary = " | ".join(active_reports)
            status_banner = f"DETECTADO: {summary}"
            cv2.putText(frame, status_banner, (12, h - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
        else:
            active_modes = []
            if mode_aruco: active_modes.append("ArUco")
            if mode_colors: active_modes.append("Colores")
            if mode_line: active_modes.append("Linea")
            modes_str = ", ".join(active_modes) if active_modes else "Ninguno"
            status_banner = f"Buscando: {modes_str}..."
            cv2.putText(frame, status_banner, (12, h - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (150, 160, 175), 1)

        # Indicador de estado de la Camara
        cam_dot_col = (0, 255, 0) if cam.is_connected else (0, 0, 255)
        cv2.circle(frame, (w - 325, h - 18), 5, cam_dot_col, -1)
        cam_text = "CAM: IP OK" if cam.current_mode == "IP" and cam.is_connected else ("CAM: USB OK" if cam.is_connected else "CAM: OFF")
        cv2.putText(frame, cam_text, (w - 312, h - 13), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (220, 220, 220), 1)

        # Indicador de estado del ESP32
        esp_dot_col = (0, 255, 0) if esp.is_connected else (0, 0, 255)
        cv2.circle(frame, (w - 175, h - 18), 5, esp_dot_col, -1)
        esp_short = f"{esp.port_name} OK" if esp.is_connected else "ESP32 OFF"
        cv2.putText(frame, esp_short, (w - 162, h - 13), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (220, 220, 220), 1)

        cv2.imshow(win_name, frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            break
        elif key == ord('1'):
            buttons[0]["active"] = not buttons[0]["active"]
            print(f"[TECLADO] ArUco -> {buttons[0]['active']}")
        elif key == ord('2'):
            buttons[1]["active"] = not buttons[1]["active"]
            print(f"[TECLADO] 4 Colores -> {buttons[1]['active']}")
        elif key == ord('3'):
            buttons[2]["active"] = not buttons[2]["active"]
            print(f"[TECLADO] Linea Verde -> {buttons[2]['active']}")
        elif key == ord('m') or key == ord('M'):
            buttons[3]["active"] = not buttons[3]["active"]
            print(f"[TECLADO] Modo Espejo -> {buttons[3]['active']}")
        elif key == ord('c') or key == ord('C'):
            cam.switch_source()

    cam.release()
    cv2.destroyAllWindows()
    esp.close()
    print("[SALIDA] Detector finalizado.")

if __name__ == '__main__':
    main()
