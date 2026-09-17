#!/usr/bin/env python3
"""
ip_webcam.py — HP Android jadi webcam via WiFi (low-latency).

Fix delay: background thread terus-menerus baca frame dari stream
sehingga main thread selalu dapat frame TERBARU, bukan frame yang
udah numpuk di buffer OpenCV.

Cara pakai:
  1. Install "IP Webcam" di Android (gratis, Play Store)
  2. Buka app → Start server → catat URL-nya (mis: http://192.168.1.5:8080)
  3. Di IP Webcam app: Settings → Video preferences → Resolution → 720p
     (lebih rendah = lebih smooth, 1080p sering lag di WiFi 2.4GHz)
  4. Jalankan:
       python ip_webcam.py http://192.168.1.5:8080 -k kunci_jawaban.csv
"""

import sys, os, argparse, time, threading
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run


# ── Low-latency frame reader (fix utama untuk delay) ─────────────────────────
class _LatestFrame:
    """
    Background thread terus-menerus drain buffer kamera.
    Main thread cukup ambil frame terbaru tanpa nunggu antrian.
    Ini solusi standar untuk menekan lag kamera IP / MJPEG.
    """

    def __init__(self, url: str):
        self._cap   = cv2.VideoCapture(url)
        self._frame = None
        self._lock  = threading.Lock()
        self._alive = True
        t = threading.Thread(target=self._drain, daemon=True)
        t.start()

    def _drain(self):
        while self._alive:
            ok, f = self._cap.read()
            if ok:
                with self._lock:
                    self._frame = f

    # ── Interface sama seperti cv2.VideoCapture ──────────────────────────────
    def read(self):
        with self._lock:
            f = self._frame
        if f is None:
            return False, None
        return True, f.copy()

    def isOpened(self):
        return self._cap.isOpened()

    def set(self, prop, val):
        return self._cap.set(prop, val)

    def get(self, prop):
        return self._cap.get(prop)

    def release(self):
        self._alive = False
        time.sleep(0.2)
        self._cap.release()


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="OMR lewat kamera HP Android (IP Webcam, low-latency)")
    ap.add_argument("url",         help="URL IP Webcam, contoh: http://192.168.1.5:8080")
    ap.add_argument("-k","--key",  help="File kunci jawaban CSV")
    ap.add_argument("--save-dir",  default="hasil_scan")
    ap.add_argument("--manual",    action="store_true", help="Matikan auto-jepret")
    args = ap.parse_args()

    # Muat kunci
    key = {}
    if args.key:
        key = run.load_key(args.key)
        print(f"✓ Kunci jawaban: {len(key)} soal" if key
              else f"⚠  Kunci '{args.key}' tidak terbaca — lanjut tanpa nilai")

    # Bangun URL video MJPEG
    base = args.url.rstrip("/")
    video_url = base if base.endswith("/video") else base + "/video"

    print(f"\n  Menghubungi {video_url} …")

    # Uji koneksi dulu sebelum run_webcam
    test = cv2.VideoCapture(video_url)
    deadline = time.time() + 8
    while not test.isOpened() and time.time() < deadline:
        time.sleep(0.4)
    if not test.isOpened():
        print("ERROR: tidak bisa terhubung ke kamera HP.")
        print("  • Pastikan HP & PC di WiFi yang SAMA")
        print(f"  • Coba buka {base} di browser PC — kalau muncul feed kamera, URL benar")
        print("  • Di IP Webcam app, pastikan sudah tekan 'Start server'")
        test.release(); return
    test.release()
    print("✓ Kamera HP terdeteksi!\n")

    # Patch cv2.VideoCapture → _LatestFrame saat run_webcam buka kamera
    _orig = cv2.VideoCapture
    def _patched(index, *a, **kw):
        print("  → Membuka stream kamera HP (low-latency mode)…")
        return _LatestFrame(video_url)
    cv2.VideoCapture = _patched

    print("""╔══════════════════════════════════════════╗
║    OMR via IP Webcam — low-latency       ║
╠══════════════════════════════════════════╣
║  SPASI  → jepret manual                  ║
║  Q/ESC  → keluar                         ║
║                                          ║
║  Tip: di app IP Webcam set resolusi      ║
║  720p supaya frame rate lebih tinggi.    ║
╚══════════════════════════════════════════╝
""")

    try:
        run.run_webcam(0, key, args.save_dir, auto=not args.manual)
    finally:
        cv2.VideoCapture = _orig


if __name__ == "__main__":
    main()
