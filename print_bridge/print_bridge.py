import os
import re
import sys
import json
import socket
import base64
import tempfile
import urllib.parse
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import requests
from PIL import Image, ImageOps
import fitz

PORT = int(os.environ.get("PRINT_BRIDGE_PORT", 5050))
HOST = os.environ.get("PRINT_BRIDGE_HOST", "0.0.0.0")
SITES_DIR = Path("/home/hns/erpnext/sites")


def is_ip_printer(printer_name):
    clean = re.sub(r":\d+$", "", str(printer_name or "").strip())
    ipv4 = r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    return bool(re.match(ipv4, clean))


def parse_ip_port(printer_name, default_port=9100):
    match = re.match(r"^([^:]+)(?::(\d+))?$", str(printer_name or "").strip())
    if not match:
        return None, default_port
    host = match.group(1)
    port = int(match.group(2)) if match.group(2) else default_port
    return host, port


def send_socket_data(host, port, data_bytes, timeout=10):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect((host, port))
        s.sendall(data_bytes)


def image_to_zpl(img):
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.convert("RGBA").split()[3])
        img = bg
    w, h = img.size
    mono = ImageOps.invert(img.convert("L")).convert("1")
    bytes_per_row = (w + 7) // 8
    total_bytes = bytes_per_row * h
    hex_data = mono.tobytes().hex().upper()
    return f"^XA^PW{w}^LL{h}^FO0,0^GFA,{total_bytes},{total_bytes},{bytes_per_row},{hex_data}^FS^XZ"


def pdf_to_zpl(pdf_path):
    doc = fitz.open(pdf_path)
    zpl_parts = []
    for page in doc:
        pix = page.get_pixmap()
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        zpl_parts.append(image_to_zpl(img))
    return "\n".join(zpl_parts)


def convert_file_to_zpl(local_file_path):
    ext = Path(local_file_path).suffix.lower()
    if ext in [".zpl", ".prn", ".txt", ".lbl"]:
        with open(local_file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    if ext == ".pdf":
        return pdf_to_zpl(local_file_path)

    if ext in [".png", ".jpg", ".jpeg", ".bmp", ".webp"]:
        with Image.open(local_file_path) as img:
            return image_to_zpl(img)

    with open(local_file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    if content.strip().startswith("^XA"):
        return content
    return pdf_to_zpl(local_file_path)


def resolve_local_file_path(file_url_or_path):
    raw = str(file_url_or_path or "").strip()
    if os.path.exists(raw):
        return raw

    match = re.search(r"/(private/files/[^?#]+|files/[^?#]+)", raw)
    if match and SITES_DIR.exists():
        rel = match.group(1)
        for site in SITES_DIR.iterdir():
            if site.is_dir():
                if rel.startswith("private/"):
                    cand = site / rel
                else:
                    cand = site / "public" / rel
                if cand.exists():
                    return str(cand)

    return None


class PrintBridgeHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code, data):
        response_bytes = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(response_bytes)

    def do_OPTIONS(self):
        self._send_json(200, {"status": "ok"})

    def do_GET(self):
        if self.path in ["/health", "/", "/status"]:
            self._send_json(200, {"status": "ok", "service": "print_bridge", "port": PORT})
        else:
            self._send_json(404, {"success": False, "message": "Not Found"})

    def do_POST(self):
        if self.path not in ["/print", "/api/print"]:
            self._send_json(404, {"success": False, "message": "Endpoint not found"})
            return

        temp_file = None
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else ""

            content_type = self.headers.get("Content-Type", "")
            if "application/json" in content_type:
                data = json.loads(body) if body else {}
            elif "application/x-www-form-urlencoded" in content_type or "=" in body:
                parsed = urllib.parse.parse_qs(body)
                data = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}
            else:
                try:
                    data = json.loads(body)
                except Exception:
                    data = {}

            printer = data.get("printer") or data.get("printer_name")
            file_url = data.get("file_url")
            file_path = data.get("file_path")
            file_base64 = data.get("data_base64")

            if not printer:
                self._send_json(400, {"success": False, "message": "Missing 'printer' parameter"})
                return

            if not file_path and file_url:
                local_cand = resolve_local_file_path(file_url)
                if local_cand:
                    file_path = local_cand

            if not file_path:
                if file_url:
                    resp = requests.get(file_url, timeout=15)
                    if resp.status_code != 200:
                        self._send_json(400, {"success": False, "message": f"Failed to download file from {file_url}: HTTP {resp.status_code}"})
                        return
                    ext = Path(file_url.split("?")[0]).suffix or ".pdf"
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
                    temp_file.write(resp.content)
                    temp_file.close()
                    file_path = temp_file.name

                elif file_base64:
                    raw_bytes = base64.b64decode(file_base64)
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
                    temp_file.write(raw_bytes)
                    temp_file.close()
                    file_path = temp_file.name
                else:
                    self._send_json(400, {"success": False, "message": "Provide either 'file_path', 'file_url', or 'data_base64'"})
                    return

            if not os.path.exists(file_path):
                self._send_json(400, {"success": False, "message": f"File does not exist: {file_path}"})
                return

            host, port = parse_ip_port(printer)
            zpl_data = convert_file_to_zpl(file_path)
            send_socket_data(host, port, zpl_data.encode("utf-8"))
            self._send_json(200, {"success": True, "message": f"Printed directly to IP printer {host}:{port}"})

        except Exception as e:
            self._send_json(500, {"success": False, "message": str(e)})
        finally:
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.remove(temp_file.name)
                except Exception:
                    pass


def run_server():
    server = ThreadingHTTPServer((HOST, PORT), PrintBridgeHandler)
    print(f"[+] Print Bridge Microservice running on http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down Print Bridge.")
        server.server_close()


if __name__ == "__main__":
    run_server()
