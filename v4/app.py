#!/usr/bin/env python3
"""
app.py — OMR Web Scanner
PC jalan server Flask, HP Android akses via browser Chrome.

Cara akses dari HP Android (3 pilihan, pilih salah satu):

  [A] HTTP + Chrome flag — TERMUDAH
      1. python app.py --http
      2. Di Chrome Android buka: chrome://flags/#unsafely-treat-insecure-origin-as-secure
      3. Tambahkan: http://IP_PC:8765  →  Relaunch Chrome
      4. Buka http://IP_PC:8765

  [B] ngrok HTTPS — PALING SIMPEL, butuh internet
      1. pip install pyngrok  lalu  python app.py --ngrok
      2. Copy URL https://xxxx.ngrok-free.app yang muncul di terminal
      3. Buka di Chrome Android → langsung jalan, kamera langsung aktif

  [C] HTTPS self-signed — TANPA internet
      1. python app.py
      2. Buka https://IP_PC:8765 di Chrome Android
      3. Muncul peringatan? → tap "Lanjutan" → "Lanjutkan ke IP (tidak aman)"
         Kalau tombol itu tidak muncul, coba [A] atau [B].

Usage:
  python app.py                      # HTTPS self-signed (default)
  python app.py --http               # HTTP biasa (pakai metode [A])
  python app.py --ngrok              # HTTPS via ngrok (metode [B])
  python app.py -k soal_lain.csv
  python app.py --port 8080
"""

import os, sys, socket, base64, argparse
import cv2
import numpy as np
from flask import Flask, request, jsonify, render_template

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run import scan_frame, grade, load_key, build_overlay_image

app = Flask(__name__)
key = {}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def status():
    return jsonify({"key_loaded": bool(key), "total_questions": len(key)})


@app.route("/api/scan", methods=["POST"])
def scan():
    try:
        b64 = request.json.get("image", "")
        if "," in b64:
            b64 = b64.split(",")[1]
        nparr = np.frombuffer(base64.b64decode(b64), np.uint8)
        img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({"success": False, "error": "Gambar tidak bisa dibaca"})

        answers, warped = scan_frame(img)

        out = {"success": True, "answers": {
            str(no): {"letter": letter, "status": st}
            for no, (letter, st, _) in answers.items()
        }}

        if key:
            r = grade(answers, key)
            out["grade"] = {
                "nilai": r["nilai"], "benar": r["benar"],
                "salah": r["salah"], "kosong": r["kosong"],
                "ragu":  r["ragu"],  "total":  r["total"],
                "detail": [
                    {"no": no, "kunci": k, "jawaban": j, "hasil": h}
                    for no, k, j, h in r["detail"]
                ],
            }
            ov = build_overlay_image(warped, answers, key)
            _, buf = cv2.imencode(".jpg", ov, [cv2.IMWRITE_JPEG_QUALITY, 88])
            out["overlay"] = "data:image/jpeg;base64," + base64.b64encode(buf).decode()

        return jsonify(out)

    except RuntimeError as e:
        return jsonify({"success": False, "error": str(e)})
    except Exception as e:
        return jsonify({"success": False, "error": f"Error: {e}"})


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def run_with_ngrok(port):
    try:
        from pyngrok import ngrok
    except ImportError:
        print("ERROR: pyngrok belum terinstall. Jalankan: pip install pyngrok")
        sys.exit(1)

    http_tunnel = ngrok.connect(port, "http")
    url = http_tunnel.public_url.replace("http://", "https://")
    print(f"""
╔═══════════════════════════════════════════════╗
║      OMR Web Scanner — via ngrok              ║
╠═══════════════════════════════════════════════╣
║  Buka di Chrome Android:                      ║
║  {url:<45} ║
║                                               ║
║  (URL berlaku selama session ini aktif)        ║
╚═══════════════════════════════════════════════╝
""")
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="OMR Web Scanner")
    ap.add_argument("-k", "--key",    default="kunci_jawaban.csv")
    ap.add_argument("-p", "--port",   type=int, default=8765)
    ap.add_argument("--http",         action="store_true",
                    help="HTTP biasa (pakai Chrome flag untuk izin kamera)")
    ap.add_argument("--ngrok",        action="store_true",
                    help="Tunnel HTTPS via ngrok (butuh: pip install pyngrok)")
    args = ap.parse_args()

    # Muat kunci
    kp = args.key
    if os.path.exists(kp):
        key = load_key(kp)
        print(f"✓ Kunci jawaban: {len(key)} soal dari '{kp}'")
    else:
        print(f"⚠  Kunci tidak ditemukan: {kp}  (lanjut tanpa nilai)")

    if args.ngrok:
        run_with_ngrok(args.port)
    else:
        ip    = get_local_ip()
        proto = "http" if args.http else "https"
        ssl   = None if args.http else "adhoc"

        tip_a = (
            "Kamera aktif langsung ✓" if args.http
            else "Kalau muncul peringatan → tap 'Lanjutan' → 'Lanjutkan ke IP'"
        )

        print(f"""
╔═══════════════════════════════════════════════╗
║      OMR Web Scanner — siap!                  ║
╠═══════════════════════════════════════════════╣
║  Buka di Chrome Android (WiFi sama):          ║
║  {proto}://{ip}:{args.port:<29} ║
║                                               ║
║  {tip_a:<45} ║
║                                               ║
║  Firewall Windows block? Jalankan di CMD:     ║
║  netsh advfirewall firewall add rule          ║
║    name="OMR" dir=in action=allow             ║
║    protocol=TCP localport={args.port}              ║
╚═══════════════════════════════════════════════╝
""")
        app.run(host="0.0.0.0", port=args.port, ssl_context=ssl, debug=False)
