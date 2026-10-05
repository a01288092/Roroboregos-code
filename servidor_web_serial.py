import http.server
import socketserver
import os
import webbrowser
import urllib.parse
import urllib.request
import base64

PORT = 8000

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def get_auth_header(self, url, user=None, password=None):
        parsed = urllib.parse.urlsplit(url)
        u = user or parsed.username
        p = password or parsed.password
        if u and p is not None:
            token = base64.b64encode(f"{u}:{p}".encode("utf-8")).decode("ascii")
            return f"Basic {token}"
        return None

    def clean_target_url(self, url):
        parsed = urllib.parse.urlsplit(url)
        scheme = parsed.scheme or "http"
        netloc = parsed.hostname or "127.0.0.1"
        if parsed.port:
            netloc += f":{parsed.port}"
        path = parsed.path or "/"
        query = f"?{parsed.query}" if parsed.query else ""
        return f"{scheme}://{netloc}{path}{query}"

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.path = "/aruco_grid.html"
            return super().do_GET()
        elif self.path.startswith("/proxy_shot"):
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            target_url = params.get("url", [None])[0]
            user = params.get("user", [None])[0]
            password = params.get("pass", [None])[0]

            if not target_url:
                self.send_error(400, "Falta parametro url")
                return

            if not target_url.startswith("http://") and not target_url.startswith("https://"):
                target_url = "http://" + target_url

            auth_header = self.get_auth_header(target_url, user, password)
            clean_url = self.clean_target_url(target_url)

            # Probar candidatos para obtener un fotograma JPG valido
            candidate_urls = [clean_url]
            parsed = urllib.parse.urlsplit(clean_url)
            if parsed.path in ("", "/"):
                candidate_urls = [
                    f"{parsed.scheme}://{parsed.netloc}/snapshot.jpg",
                    f"{parsed.scheme}://{parsed.netloc}/shot.jpg",
                    f"{parsed.scheme}://{parsed.netloc}/video",
                    clean_url
                ]

            data = None
            content_type = "image/jpeg"
            last_err = None

            for url in candidate_urls:
                try:
                    headers = {"User-Agent": "Mozilla/5.0"}
                    if auth_header:
                        headers["Authorization"] = auth_header
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=2.5) as resp:
                        ct = resp.headers.get("Content-Type", "")
                        if "text/html" in ct and url != candidate_urls[-1]:
                            continue
                        data = resp.read()
                        content_type = ct or "image/jpeg"
                        break
                except Exception as e:
                    last_err = e
                    continue

            if data:
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.end_headers()
                self.wfile.write(data)
                return
            else:
                self.send_response(502)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(f"Error al conectar con camara IP: {last_err}".encode())
                return

        elif self.path.startswith("/proxy_stream"):
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            target_url = params.get("url", [None])[0]
            user = params.get("user", [None])[0]
            password = params.get("pass", [None])[0]

            if not target_url:
                self.send_error(400, "Falta parametro url")
                return

            if not target_url.startswith("http://") and not target_url.startswith("https://"):
                target_url = "http://" + target_url

            auth_header = self.get_auth_header(target_url, user, password)
            clean_url = self.clean_target_url(target_url)

            parsed = urllib.parse.urlsplit(clean_url)
            if parsed.path in ("", "/"):
                clean_url = f"{parsed.scheme}://{parsed.netloc}/video"

            try:
                headers = {"User-Agent": "Mozilla/5.0"}
                if auth_header:
                    headers["Authorization"] = auth_header
                req = urllib.request.Request(clean_url, headers=headers)
                resp = urllib.request.urlopen(req, timeout=5.0)

                ct = resp.headers.get("Content-Type", "multipart/x-mixed-replace; boundary=boundarydonotcross")
                self.send_response(200)
                self.send_header("Content-Type", ct)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.end_headers()

                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
                return
            except (BrokenPipeError, ConnectionResetError):
                return
            except Exception as e:
                self.send_response(502)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(f"Error en stream IP: {e}".encode())
                return

        return super().do_GET()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def log_message(self, format, *args):
        pass

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    socketserver.TCPServer.allow_reuse_address = True
    server_address = ("0.0.0.0", PORT)
    try:
        httpd = http.server.ThreadingHTTPServer(server_address, CustomHandler)
    except Exception as e:
        print(f"Error abriendo puerto {PORT}: {e}")
        return

    url = f"http://localhost:{PORT}/"
    print("=======================================================")
    print("  SERVIDOR WEB LOCAL CON PROXY DE CAMARA IP (AUTH)     ")
    print("=======================================================")
    print(f"Servidor activo en: {url}")
    print("Soporte para Galaxy Tab A y camaras IP con usuario y contrasena.")
    print("El puerto COM13 queda 100% libre para WebSerial.")
    print("\nPresiona Ctrl+C para cerrar.")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nCerrando servidor...")
        httpd.server_close()

if __name__ == '__main__':
    main()
