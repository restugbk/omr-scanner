#!/usr/bin/env python3
"""
OMR Web Scanner — jalankan di PC Windows, akses dari HP Android via browser.
Tidak perlu install apapun di HP, cukup buka URL di Chrome/browser.

Usage:
    python app.py                          # pakai kunci_jawaban.csv default
    python app.py --key soal_lain.csv      # kunci lain
    python app.py --no-ssl                 # HTTP biasa (lihat catatan di bawah)
    python app.py --port 8080              # port lain
"""

import os, sys, socket, base64, argparse
import cv2
import numpy as np
from flask import Flask, request, jsonify, render_template

# ─── import semua logic OMR dari run.py yang sudah ada ───────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run import scan_frame, grade, load_key, build_overlay_image

# ─────────────────────────────────────────────────────────────────────────────
app  = Flask(__name__)
key  = {}          # diisi saat startup


# ── Endpoint utama ────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def status():
    return jsonify({"key_loaded": bool(key), "total_questions": len(key)})


@app.route("/api/scan", methods=["POST"])
def scan():
    try:
        img_b64 = request.json.get("image", "")
        if "," in img_b64:
            img_b64 = img_b64.split(",")[1]

        nparr = np.frombuffer(base64.b64decode(img_b64), np.uint8)
        img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({"success": False, "error": "Gambar tidak bisa dibaca"})

        answers, warped = scan_frame(img)

        out = {"success": True, "answers": {
            str(no): {"letter": letter, "status": status}
            for no, (letter, status, _) in answers.items()
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
            # overlay image → base64 JPEG
            ov = build_overlay_image(warped, answers, key)
            _, buf = cv2.imencode(".jpg", ov, [cv2.IMWRITE_JPEG_QUALITY, 88])
            out["overlay"] = "data:image/jpeg;base64," + base64.b64encode(buf).decode()

        return jsonify(out)

    except RuntimeError as e:
        return jsonify({"success": False, "error": str(e)})
    except Exception as e:
        return jsonify({"success": False, "error": f"Error: {e}"})


# ── Startup ────────────────────────────────────────────────────────────────────
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="OMR Web Scanner")
    ap.add_argument("-k", "--key",    default="kunci_jawaban.csv")
    ap.add_argument("-p", "--port",   type=int, default=5000)
    ap.add_argument("--no-ssl",       action="store_true",
                    help="Gunakan HTTP biasa (kamera mungkin diblokir browser di HP)")
    args = ap.parse_args()

    # Muat kunci
    key_path = args.key
    if os.path.exists(key_path):
        key = load_key(key_path)
        print(f"✓ Kunci jawaban dimuat dari '{key_path}': {len(key)} soal")
    else:
        print(f"⚠  File kunci tidak ditemukan: {key_path}  (lanjut tanpa nilai)")

    local_ip   = get_local_ip()
    proto      = "http" if args.no_ssl else "https"
    ssl_ctx    = None if args.no_ssl else "adhoc"   # self-signed cert otomatis

    print(f"""
╔══════════════════════════════════════════════╗
║          OMR Web Scanner — siap!             ║
╠══════════════════════════════════════════════╣
║  Buka di HP Android (WiFi sama):             ║
║  {proto}://{local_ip}:{args.port:<27}   ║
║                                              ║
║  Tip: Chrome Android → "Lanjutkan"           ║
║  kalau muncul peringatan HTTPS.              ║
╚══════════════════════════════════════════════╝
""")

    app.run(host="0.0.0.0", port=args.port, ssl_context=ssl_ctx, debug=False)
