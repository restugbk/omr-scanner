#!/usr/bin/env python3
import cv2
import numpy as np
import csv
import argparse
import sys
import os
import time

# ============================ KONFIGURASI ===================================
# (Biasanya tidak perlu diubah. Sesuai format lembar jawaban kamu.)
OPTIONS      = ['A', 'B', 'C', 'D', 'E']   # opsi jawaban tiap soal (baris A-E)
QPG          = 30                           # jumlah soal per blok grid
NUM_GRIDS    = 2                            # ada 2 blok: 1-30 dan 31-60

# --- Ambang deteksi (ubah HANYA kalau hasil baca kurang akurat) -------------
FILL_MIN     = 0.05   # minimal "tinta" dalam sel agar dianggap ada tanda (0..1)
WINNER_GAP   = 0.04   # selisih min pemenang vs pesaing; di bawah ini -> RAGU
CELL_SHRINK  = 0.16   # potong tepi tiap sel agar tidak kena garis grid
PROC_WIDTH   = 1400   # lebar gambar saat diproses (auto-resize)

# --- Khusus WEBCAM (silakan diutak-atik kalau perlu) ------------------------
CAM_WIDTH     = 1280  # resolusi yg diminta ke kamera (makin tinggi makin tajam)
CAM_HEIGHT    = 720
PREVIEW_WIDTH = 900   # lebar utk deteksi-grid versi preview (biar live feed enteng)
PREVIEW_EVERY = 4     # cek grid tiap N frame (biar gak berat)
STABLE_NEED   = 6     # berapa kali deteksi stabil sebelum AUTO-jepret
# ===========================================================================


# --------------------------- util geometri ---------------------------------
def order_quad(pts):
    """Urutkan 4 titik jadi: kiri-atas, kanan-atas, kanan-bawah, kiri-bawah."""
    pts = pts.reshape(-1, 2).astype(np.float32)
    s = pts.sum(1)
    d = np.diff(pts, 1).reshape(-1)
    return np.array([pts[np.argmin(s)], pts[np.argmin(d)],
                     pts[np.argmax(s)], pts[np.argmax(d)]], np.float32)


def line_peaks(profile, min_gap):
    """Cari posisi garis dari profil proyeksi (puncak yg dipisah min_gap)."""
    prof = profile.astype(float)
    if prof.max() <= 0:
        return []
    idx = np.where(prof > prof.max() * 0.35)[0]
    if len(idx) == 0:
        return []
    grp = [[idx[0]]]
    for i in idx[1:]:
        if i - grp[-1][-1] <= min_gap:
            grp[-1].append(i)
        else:
            grp.append([i])
    return [int(np.mean(g)) for g in grp]


def refine_lines(centers, expected):
    """Paksa jumlah garis = expected: gabung yg terlalu rapat / sisipkan yg hilang."""
    c = sorted(centers)
    if len(c) < 2:
        return c
    while len(c) > expected:
        gaps = [c[i + 1] - c[i] for i in range(len(c) - 1)]
        j = int(np.argmin(gaps))
        c[j] = (c[j] + c[j + 1]) // 2
        del c[j + 1]
    while len(c) < expected:
        gaps = [c[i + 1] - c[i] for i in range(len(c) - 1)]
        j = int(np.argmax(gaps))
        c.insert(j + 1, (c[j] + c[j + 1]) // 2)
    return c


# --------------------------- deteksi grid ----------------------------------
def _grid_mask(small):
    g = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (3, 3), 0)
    th = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                               cv2.THRESH_BINARY_INV, 25, 12)
    hk = cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, small.shape[1] // 40), 1))
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(15, small.shape[0] // 40)))
    hor = cv2.morphologyEx(th, cv2.MORPH_OPEN, hk)
    ver = cv2.morphologyEx(th, cv2.MORPH_OPEN, vk)
    return cv2.dilate(cv2.bitwise_or(hor, ver), np.ones((3, 3), np.uint8), iterations=2)


def find_grids(small):
    """Temukan blok-blok grid jawaban (kotak lebar). Diurutkan atas -> bawah."""
    mask = _grid_mask(small)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    area_img = small.shape[0] * small.shape[1]
    cands = []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if w * h > 0.04 * area_img and w / float(h) > 2.5:   # grid jawaban = lebar
            cands.append(c)
    cands.sort(key=lambda c: cv2.boundingRect(c)[2] * cv2.boundingRect(c)[3], reverse=True)
    cands = cands[:NUM_GRIDS]
    cands.sort(key=lambda c: cv2.boundingRect(c)[1])         # atas -> bawah
    return cands


def warp_grid(small, contour):
    """Luruskan satu grid (perspective warp) + temukan garis sel sebenarnya."""
    COLS, ROWS = QPG + 1, len(OPTIONS) + 1
    CW = CH = 48
    PAD = 10
    W2, H2 = COLS * CW, ROWS * CH
    hull = cv2.convexHull(contour)
    ap = cv2.approxPolyDP(hull, 0.02 * cv2.arcLength(hull, True), True)
    quad = order_quad(ap if len(ap) == 4 else hull)
    dst = np.array([[PAD, PAD], [W2 - PAD, PAD],
                    [W2 - PAD, H2 - PAD], [PAD, H2 - PAD]], np.float32)
    warp = cv2.warpPerspective(small, cv2.getPerspectiveTransform(quad, dst), (W2, H2))

    wg = cv2.cvtColor(warp, cv2.COLOR_BGR2GRAY)
    wth = cv2.adaptiveThreshold(wg, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                cv2.THRESH_BINARY_INV, 25, 12)
    wh = cv2.morphologyEx(wth, cv2.MORPH_OPEN,
                          cv2.getStructuringElement(cv2.MORPH_RECT, (W2 // 40, 1)))
    wv = cv2.morphologyEx(wth, cv2.MORPH_OPEN,
                          cv2.getStructuringElement(cv2.MORPH_RECT, (1, H2 // 30)))
    xs = refine_lines(line_peaks(wv.sum(0), CW // 2), COLS + 1)
    ys = refine_lines(line_peaks(wh.sum(1), CH // 2), ROWS + 1)
    # fallback kalau deteksi garis gagal: bagi rata
    if len(xs) != COLS + 1:
        xs = [int(round(PAD + i * (W2 - 2 * PAD) / COLS)) for i in range(COLS + 1)]
    if len(ys) != ROWS + 1:
        ys = [int(round(PAD + i * (H2 - 2 * PAD) / ROWS)) for i in range(ROWS + 1)]

    marks = cv2.subtract(wth, cv2.bitwise_or(wh, wv))         # tanda saja (tanpa garis)
    marks = cv2.morphologyEx(marks, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    return warp, xs, ys, marks


def read_grid(xs, ys, marks, grid_index):
    """Baca jawaban tiap soal dalam satu grid.
    Return dict: nomor_soal -> (letter|None, status, fills)
      status: 'OK' / 'KOSONG' / 'RAGU'
    """
    ROWS = len(OPTIONS) + 1
    out = {}
    for col in range(1, QPG + 1):                # lewati kolom label (col 0)
        fills = []
        for row in range(1, ROWS):               # lewati baris header (row 0)
            x0, x1 = xs[col], xs[col + 1]
            y0, y1 = ys[row], ys[row + 1]
            mx = int((x1 - x0) * CELL_SHRINK)
            my = int((y1 - y0) * CELL_SHRINK)
            roi = marks[y0 + my:y1 - my, x0 + mx:x1 - mx]
            fills.append(roi.mean() / 255.0 if roi.size else 0.0)
        fills = np.array(fills)
        best = int(fills.argmax())
        srt = np.sort(fills)[::-1]
        qno = grid_index * QPG + col
        if srt[0] < FILL_MIN:
            out[qno] = (None, 'KOSONG', fills)
        elif srt[1] >= FILL_MIN and (srt[0] - srt[1]) < WINNER_GAP:
            out[qno] = (OPTIONS[best], 'RAGU', fills)        # dua tanda mirip kuat
        else:
            out[qno] = (OPTIONS[best], 'OK', fills)
    return out


# --------------------------- pipeline utama --------------------------------
def scan_frame(img):
    """INTI pembacaan satu gambar (array BGR).
       Isinya SAMA PERSIS dengan scan_sheet lama; bedanya menerima array
       (bukan path file), supaya bisa dipakai mode FOTO maupun WEBCAM."""
    H, W = img.shape[:2]
    scale = PROC_WIDTH / float(W)
    small = cv2.resize(img, (int(W * scale), int(H * scale)))

    grids = find_grids(small)
    if len(grids) < NUM_GRIDS:
        raise RuntimeError(
            f"Hanya terdeteksi {len(grids)} grid (butuh {NUM_GRIDS}). "
            "Lembar kurang lurus/terang. Geser biar 2 grid kelihatan penuh & rata.")

    answers = {}
    warped = []   # simpan utk gambar verifikasi
    for gi, c in enumerate(grids):
        warp, xs, ys, marks = warp_grid(small, c)
        answers.update(read_grid(xs, ys, marks, gi))
        warped.append((warp, xs, ys))
    return answers, warped


def scan_sheet(image_path):
    """Mode FOTO: baca dari file, lalu lempar ke scan_frame (logika sama)."""
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Gambar tidak terbaca: {image_path}")
    return scan_frame(img)


# --------------------------- kunci & penilaian -----------------------------
def load_key(path):
    """Baca kunci jawaban dari CSV (kolom: nomor,jawaban). Return dict {no:huruf}."""
    key = {}
    with open(path, newline='', encoding='utf-8-sig') as f:
        for row in csv.reader(f):
            if not row or not row[0].strip():
                continue
            a = row[0].strip().lower()
            if a in ('nomor', 'no', 'soal', 'number'):    # lewati header
                continue
            try:
                no = int(row[0])
            except ValueError:
                continue
            ans = row[1].strip().upper() if len(row) > 1 else ''
            if ans in OPTIONS:
                key[no] = ans
    return key


def grade(answers, key):
    benar, salah, kosong, ragu = 0, 0, 0, 0
    detail = []
    for no in sorted(key):
        kunci = key[no]
        letter, status, _ = answers.get(no, (None, 'KOSONG', None))
        if status == 'KOSONG':
            hasil = 'KOSONG'; kosong += 1
        elif status == 'RAGU':
            hasil = 'RAGU'; ragu += 1
        elif letter == kunci:
            hasil = 'BENAR'; benar += 1
        else:
            hasil = 'SALAH'; salah += 1
        detail.append((no, kunci, letter, hasil))
    total = len(key)
    # nilai = round(benar / total * 100) if total else 0
    nilai = round(benar * 2 + 15) if total else 0
    return dict(benar=benar, salah=salah, kosong=kosong, ragu=ragu,
                total=total, nilai=nilai, detail=detail)


# --------------------------- gambar verifikasi -----------------------------
def build_overlay_image(warped, answers, key=None):
    """Bangun gambar verifikasi (2 grid ditumpuk) dan KEMBALIKAN array-nya.
       hijau=benar, merah=salah/kosong, oranye=ragu, abu=tanpa-kunci.
       (Isinya sama dgn make_overlay lama, cuma dipisah biar bisa
        ditampilkan langsung di window webcam tanpa harus simpan file dulu.)"""
    canvases = []
    for gi, (warp, xs, ys) in enumerate(warped):
        vis = warp.copy()
        for col in range(1, QPG + 1):
            no = gi * QPG + col
            letter, status, _ = answers.get(no, (None, 'KOSONG', None))
            cx = int((xs[col] + xs[col + 1]) / 2)
            if status in ('OK', 'RAGU') and letter in OPTIONS:
                ri = OPTIONS.index(letter) + 1
                cy = int((ys[ri] + ys[ri + 1]) / 2)
            else:
                cy = int((ys[1] + ys[-1]) / 2)
            # tentukan warna
            if key is None:
                color = (0, 180, 0) if status == 'OK' else (0, 160, 230)
            elif no not in key:
                color = (160, 160, 160)
            elif status == 'KOSONG':
                color = (40, 40, 230)
            elif status == 'RAGU':
                color = (0, 160, 230)
            elif letter == key[no]:
                color = (0, 180, 0)
            else:
                color = (40, 40, 230)
            if status == 'KOSONG':
                cv2.rectangle(vis, (xs[col] + 2, ys[1] + 2),
                              (xs[col + 1] - 2, ys[-1] - 2), color, 2)
            else:
                cv2.circle(vis, (cx, cy), 12, color, 3)
            # kalau salah, tulis kunci yg benar di atas sel
            if key is not None and no in key and status == 'OK' and letter != key[no]:
                cv2.putText(vis, key[no], (cx - 7, ys[1] - 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 130, 0), 2)
        canvases.append(vis)
    # samakan lebar lalu tumpuk
    w = max(c.shape[1] for c in canvases)
    canvases = [cv2.copyMakeBorder(c, 14, 14, 0, w - c.shape[1],
                cv2.BORDER_CONSTANT, value=(255, 255, 255)) for c in canvases]
    return cv2.vconcat(canvases)


def make_overlay(warped, answers, key=None, out_path='verifikasi.png'):
    """Buat & SIMPAN gambar verifikasi ke file (perilaku sama seperti dulu)."""
    cv2.imwrite(out_path, build_overlay_image(warped, answers, key))
    return out_path


# --------------------------- output ke layar/console -----------------------
def print_answers(answers):
    """Cetak hasil baca jawaban (format sama persis kayak script lama)."""
    print("\n=== HASIL BACA JAWABAN ===")
    line = []
    for no in sorted(answers):
        letter, status, _ = answers[no]
        tampil = letter if letter else '-'
        if status == 'RAGU':
            tampil += '?'
        line.append(f"{no}:{tampil}")
        if no % 10 == 0:
            print("  " + "  ".join(line)); line = []
    if line:
        print("  " + "  ".join(line))


def print_score(answers, key):
    """Cetak skor (format sama persis kayak script lama). Return dict hasil grade."""
    r = grade(answers, key)
    print("\n=== SKOR ===")
    print(f"  BENAR  : {r['benar']} / {r['total']}")
    print(f"  Salah  : {r['salah']}   Kosong: {r['kosong']}   Ragu: {r['ragu']}")
    print(f"  NILAI  : {r['nilai']}")
    flag = [f"{no}({hasil})" for no, _, _, hasil in r['detail']
            if hasil in ('RAGU', 'KOSONG')]
    if flag:
        print("  Perlu dicek manual:", ", ".join(flag))
    return r


# ============================ BAGIAN WEBCAM ================================
def detect_grid_boxes(frame, width=PREVIEW_WIDTH):
    """Deteksi cepat utk PREVIEW: kembalikan kotak grid dlm koordinat frame asli.
       Pakai find_grids yg sama persis — cuma buat indikator visual & auto-jepret.
       (Pembacaan jawaban tetap dilakukan ulang di resolusi penuh saat dijepret.)"""
    H, W = frame.shape[:2]
    scale = width / float(W)
    small = cv2.resize(frame, (int(W * scale), int(H * scale)))
    boxes = []
    for c in find_grids(small):
        x, y, w, h = cv2.boundingRect(c)
        boxes.append((int(x / scale), int(y / scale),
                      int(w / scale), int(h / scale)))
    return boxes


def _banner(img, text, color):
    """Garis status semi-transparan di atas frame."""
    h, w = img.shape[:2]
    bar = img.copy()
    cv2.rectangle(bar, (0, 0), (w, 42), (0, 0, 0), -1)
    cv2.addWeighted(bar, 0.45, img, 0.55, 0, img)
    cv2.putText(img, text, (12, 28), cv2.FONT_HERSHEY_SIMPLEX,
                0.72, color, 2, cv2.LINE_AA)


def run_webcam(cam_index, key, save_dir, auto=True, overlay_base='verifikasi'):
    """Loop kamera live: deteksi -> (auto/SPASI) jepret -> koreksi -> tampil & simpan."""
    # --- buka kamera (di Windows coba CAP_DSHOW dulu biar lebih lancar) ---
    if os.name == 'nt':
        cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release(); cap = cv2.VideoCapture(cam_index)
    else:
        cap = cv2.VideoCapture(cam_index)

    if not cap.isOpened():
        print(f"ERROR: kamera index {cam_index} tidak bisa dibuka.")
        print("       Coba index lain: --camera 1  (atau 2), dan cek izin kamera.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)

    if save_dir:
        os.makedirs(save_dir, exist_ok=True)

    print("\n================ MODE WEBCAM ================")
    print("  Arahkan lembar jawaban ke kamera (2 grid harus kelihatan penuh & rata).")
    if auto:
        print("  >> Otomatis dikoreksi begitu lembar terbaca stabil.")
    print("  [SPASI] koreksi manual    [Q]/[ESC] keluar")
    print("=============================================")

    win = "OMR Webcam"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    frame_i = 0
    boxes = []
    ngrid = 0
    stable = 0
    armed = True          # boleh auto-jepret? (di-nonaktifkan stlh jepret, aktif lagi saat lembar hilang)
    count = 0             # jumlah lembar yg sudah dikoreksi

    while True:
        ok, frame = cap.read()
        if not ok:
            print("ERROR: gagal baca frame dari kamera."); break
        frame_i += 1

        # ---- deteksi grid berkala (indikator + gate auto-jepret) ----
        if frame_i % PREVIEW_EVERY == 0:
            try:
                boxes = detect_grid_boxes(frame)
            except Exception:
                boxes = []
            ngrid = len(boxes)
            if ngrid >= NUM_GRIDS:
                stable += 1
            else:
                stable = 0
                armed = True          # lembar pergi -> siap jepret lembar berikutnya

        # ---- gambar preview ----
        preview = frame.copy()
        ready = ngrid >= NUM_GRIDS
        for (x, y, w, h) in boxes:
            cv2.rectangle(preview, (x, y), (x + w, y + h),
                          (0, 200, 0) if ready else (0, 170, 255), 3)
        if ready:
            _banner(preview, f"SIAP ({ngrid}/{NUM_GRIDS}) - tahan stabil / tekan SPASI",
                    (120, 255, 120))
        else:
            _banner(preview, f"Cari lembar...  grid terbaca {ngrid}/{NUM_GRIDS}",
                    (120, 200, 255))
        cv2.putText(preview, f"Sudah dikoreksi: {count}    [SPASI]=jepret  [Q]=keluar",
                    (12, preview.shape[0] - 14), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (255, 255, 255), 2, cv2.LINE_AA)

        cv2.imshow(win, preview)
        k = cv2.waitKey(1) & 0xFF

        # ---- tentukan apakah harus jepret ----
        do_capture = False
        if k in (ord('q'), 27):
            break
        elif k == ord(' '):
            do_capture = True
        elif auto and ready and stable >= STABLE_NEED and armed:
            do_capture = True

        if not do_capture:
            continue

        # ---- JEPRET & KOREKSI (pakai scan_frame resolusi penuh) ----
        grab = frame.copy()
        _banner(preview, "Memproses...", (0, 255, 255))
        cv2.imshow(win, preview); cv2.waitKey(1)

        try:
            answers, warped = scan_frame(grab)
        except Exception as e:
            shown = grab.copy()
            _banner(shown, "GAGAL baca - pastikan 2 grid terlihat penuh", (0, 0, 255))
            cv2.imshow(win, shown); cv2.waitKey(1000)
            stable = 0
            continue

        count += 1
        print_answers(answers)
        r = print_score(answers, key) if key else None

        # ---- simpan hasil (capture mentah + gambar verifikasi) ----
        if save_dir:
            raw_path = os.path.join(save_dir, f"capture_{count:03d}.png")
            ov_path  = os.path.join(save_dir, f"{overlay_base}_{count:03d}.png")
            cv2.imwrite(raw_path, grab)
            make_overlay(warped, answers, key, ov_path)
            print(f"  Tersimpan: {ov_path}")

        # ---- tampilkan hasil di window, tunggu user lanjut ----
        overlay = build_overlay_image(warped, answers, key)
        head = _score_header(overlay.shape[1], r)
        result = cv2.vconcat([head, overlay])
        res_win = "Hasil Koreksi"
        cv2.namedWindow(res_win, cv2.WINDOW_NORMAL)
        cv2.imshow(res_win, result)
        print("  >> tekan tombol apa saja utk lanjut lembar berikutnya, [Q] utk keluar <<")
        kk = cv2.waitKey(0) & 0xFF
        cv2.destroyWindow(res_win)
        if kk in (ord('q'), 27):
            break

        armed = False    # jgn auto-jepret lembar yg sama; tunggu lembar diganti/hilang
        stable = 0

    cap.release()
    cv2.destroyAllWindows()
    print(f"\nSelesai. Total lembar dikoreksi: {count}")


def _score_header(width, r):
    """Bikin bar ringkasan skor (warna ikut nilai) utk ditaruh di atas verifikasi."""
    head = np.full((72, width, 3), 255, np.uint8)
    if r is None:
        cv2.putText(head, "Tanpa kunci - hanya baca jawaban", (14, 44),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (60, 60, 60), 2, cv2.LINE_AA)
        return head
    col = (0, 150, 0) if r['nilai'] >= 75 else \
          (0, 140, 220) if r['nilai'] >= 50 else (0, 0, 210)
    cv2.putText(head, f"NILAI {r['nilai']}   BENAR {r['benar']}/{r['total']}",
                (14, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.9, col, 2, cv2.LINE_AA)
    cv2.putText(head, f"Salah {r['salah']}   Kosong {r['kosong']}   Ragu {r['ragu']}",
                (14, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (80, 80, 80), 2, cv2.LINE_AA)
    return head


# ------------------------------- main --------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Koreksi otomatis lembar jawaban PG (OMR) - dari FOTO atau WEBCAM.")
    ap.add_argument("image", nargs='?',
                    help="(opsional) file foto/scan. KALAU KOSONG -> buka WEBCAM.")
    ap.add_argument("-k", "--key", help="file kunci jawaban CSV (nomor,jawaban)")
    ap.add_argument("-o", "--overlay", default="verifikasi.png",
                    help="nama file verifikasi (mode foto). default: verifikasi.png")
    ap.add_argument("--no-overlay", action="store_true",
                    help="jangan buat gambar verifikasi (mode foto)")
    ap.add_argument("-c", "--camera", type=int, default=0,
                    help="index kamera webcam (default 0; coba 1/2 kalau gagal)")
    ap.add_argument("--save-dir", default="hasil_scan",
                    help="folder simpan hasil mode webcam (default: hasil_scan)")
    ap.add_argument("--manual", action="store_true",
                    help="webcam: matikan auto-jepret, hanya jepret pakai SPASI")
    args = ap.parse_args()

    key = load_key(args.key) if args.key else None
    if args.key and not key:
        print(f"PERINGATAN: kunci '{args.key}' kosong/format salah. Lanjut tanpa nilai.")

    # ============== MODE WEBCAM (gak ada file gambar) ==============
    if not args.image:
        run_webcam(args.camera, key, args.save_dir, auto=not args.manual)
        return

    # ============== MODE FOTO (persis script lama) ================
    try:
        answers, warped = scan_sheet(args.image)
    except Exception as e:
        print("ERROR:", e); sys.exit(1)

    print_answers(answers)
    if key:
        print_score(answers, key)

    if not args.no_overlay:
        path = make_overlay(warped, answers, key, args.overlay)
        print(f"\nGambar verifikasi disimpan: {path}")
        print("(Buka file itu utk memastikan pembacaan sudah benar.)")


if __name__ == "__main__":
    main()
