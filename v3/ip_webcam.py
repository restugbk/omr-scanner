#!/usr/bin/env python3
"""
ip_webcam.py — Opsi A: HP Android jadi webcam via WiFi (minimal, cepat)

Cara pakai:
  1. Install app "IP Webcam" di Android (gratis, dari Play Store)
  2. Buka app → Start Server → catat URL yang muncul (misal: http://192.168.1.5:8080)
  3. Jalankan:
       python ip_webcam.py http://192.168.1.5:8080 -k kunci_jawaban.csv

Script ini HANYA menambah dukungan URL; semua logika OMR tetap dari run.py asli.
"""

import sys, os, argparse, time
import cv2

# Import semua logic dari run.py yang sudah ada
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run  # pastikan run.py ada di folder yang sama


def run_ip_webcam(stream_url: str, key: dict, save_dir: str = "hasil_scan", auto: bool = True):
    """
    Versi run_webcam yang menerima URL stream kamera HP.
    Menggantikan cv2.VideoCapture(index) dengan cv2.VideoCapture(url).
    """
    # URL feed dari IP Webcam (MJPEG)
    # App IP Webcam: http://IP:8080/video
    # DroidCam:      http://IP:4747/video   (atau pakai virtual device di Windows)
    video_url = stream_url.rstrip("/") + "/video" if not stream_url.endswith("/video") else stream_url

    print(f"\n  Menghubungi kamera di: {video_url}")
    cap = cv2.VideoCapture(video_url)

    # Beri waktu koneksi terbuka
    deadline = time.time() + 8
    while not cap.isOpened() and time.time() < deadline:
        time.sleep(0.4)

    if not cap.isOpened():
        print("ERROR: tidak bisa terhubung ke kamera HP.")
        print("  • Pastikan HP & PC terhubung ke WiFi yang SAMA.")
        print("  • Pastikan app IP Webcam sudah jalan & Start Server ditekan.")
        print(f"  • Coba buka {stream_url} di browser PC dulu — kalau muncul gambar, berarti URL benar.")
        return

    print("✓ Kamera HP terhubung!\n")

    # Setelah berhasil connect, panggil run_webcam dari run.py tapi dengan cap yang sudah dibuka.
    # Karena run_webcam buka cap sendiri, kita patch sementara cv2.VideoCapture
    # agar saat run_webcam memanggil VideoCapture(index), langsung kita kembalikan cap ini.

    cap.release()   # lepas dulu, lalu biarkan run_webcam buka stream URL-nya

    # Override cam_index dengan URL stream di argparse args
    # Cara paling bersih: panggil run_webcam dan ganti VideoCapture di dalamnya.
    # Karena run.py sudah import cv2, kita monkey-patch VideoCapture sementara.

    _orig_cap = cv2.VideoCapture

    def _patched_cap(index, *args, **kwargs):
        """Abaikan index, selalu buka stream URL kamera HP."""
        c = _orig_cap(video_url)
        # Paksa resolusi ke apa pun yang dikasih HP (tidak set WIDTH/HEIGHT)
        return c

    cv2.VideoCapture = _patched_cap
    try:
        run.run_webcam(0, key, save_dir, auto=auto)
    finally:
        cv2.VideoCapture = _orig_cap   # kembalikan setelah selesai


def main():
    ap = argparse.ArgumentParser(description="OMR lewat kamera HP Android (IP Webcam)")
    ap.add_argument("url",        help="URL server IP Webcam, contoh: http://192.168.1.5:8080")
    ap.add_argument("-k","--key", help="File kunci jawaban CSV")
    ap.add_argument("--save-dir", default="hasil_scan")
    ap.add_argument("--manual",   action="store_true", help="Matikan auto-jepret")
    args = ap.parse_args()

    key = {}
    if args.key:
        key = run.load_key(args.key)
        if not key:
            print(f"PERINGATAN: kunci '{args.key}' kosong/tidak terbaca. Lanjut tanpa nilai.")
        else:
            print(f"✓ Kunci jawaban dimuat: {len(key)} soal")

    print("""
╔══════════════════════════════════════════════╗
║       OMR via IP Webcam (Android)            ║
╠══════════════════════════════════════════════╣
║  SPASI  → jepret manual                      ║
║  Q/ESC  → keluar                             ║
╚══════════════════════════════════════════════╝
""")
    run_ip_webcam(args.url, key, args.save_dir, auto=not args.manual)


if __name__ == "__main__":
    main()
