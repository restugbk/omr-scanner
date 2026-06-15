# OMR Scanner — Koreksi Otomatis Lembar Jawaban Pilihan Ganda

Tool sederhana untuk **koreksi otomatis lembar jawaban pilihan ganda (OMR / bubble sheet)** pakai Python + OpenCV. Bisa baca dari **foto/scan** atau langsung dari **webcam (live)**. Logika pembacaan grid sama persis antara mode foto dan webcam — bedanya cuma sumber input.

Cocok buat guru/pengajar yang mau koreksi ulangan cepet tanpa scanner khusus.

## Fitur

- **Mode Webcam** — arahkan lembar ke kamera, otomatis terkoreksi begitu terbaca stabil.
- **Mode Foto** — koreksi dari file gambar (`.jpg`, `.png`, dll).
- Deteksi grid otomatis (perspective warp), jadi lembar nggak harus lurus sempurna.
- Mendukung **2 blok grid** (soal 1–30 dan 31–60).
- Deteksi status jawaban: `BENAR`, `SALAH`, `KOSONG`, dan `RAGU` (kalau ada dua tanda yang sama-sama kuat).
- **Gambar verifikasi** otomatis (hijau = benar, merah = salah/kosong, oranye = ragu) supaya bisa dicek manual.
- Skor otomatis dari kunci jawaban CSV.

## Format Lembar Jawaban

Default konfigurasi:

| Parameter | Nilai | Keterangan |
|-----------|-------|------------|
| Opsi | A–E | 5 pilihan per soal |
| Soal per grid | 30 | |
| Jumlah grid | 2 | total 60 soal |

Kalau format lembarmu beda, ubah konstanta di bagian **KONFIGURASI** di dalam script.

## Persyaratan

- Python 3.7+
- OpenCV
- NumPy

## Instalasi

```bash
git clone https://github.com/restugbk/omr-scanner.git
cd omr-scanner
pip install opencv-python numpy
```

## Cara Pakai

### Mode Webcam (default)

Nggak kasih file gambar → langsung buka kamera:

```bash
python omr_webcam.py -k kunci_jawaban.csv
```

Di mode webcam:
- Arahkan lembar jawaban ke kamera (usahakan 2 grid kelihatan penuh & rata).
- Begitu terbaca stabil → **otomatis** dikoreksi.
- `[SPASI]` → koreksi manual kapan saja.
- `[Q]` / `[ESC]` → keluar.

### Mode Foto

Kasih file gambarnya:

```bash
python omr_webcam.py lembar.jpg -k kunci_jawaban.csv
```

### Format Kunci Jawaban (CSV)

File `kunci_jawaban.csv` isinya `nomor,jawaban`:

```csv
nomor,jawaban
1,A
2,C
3,B
4,E
...
```

Header opsional — baris seperti `nomor,jawaban` otomatis dilewati.

## Opsi Command Line

| Argumen | Default | Keterangan |
|---------|---------|------------|
| `image` | — | (opsional) file foto/scan. Kosong → buka webcam |
| `-k`, `--key` | — | file kunci jawaban CSV |
| `-o`, `--overlay` | `verifikasi.png` | nama file verifikasi (mode foto) |
| `--no-overlay` | — | jangan buat gambar verifikasi |
| `-c`, `--camera` | `0` | index kamera (coba 1/2 kalau gagal) |
| `--save-dir` | `hasil_scan` | folder simpan hasil mode webcam |
| `--manual` | — | webcam: matikan auto-jepret, hanya pakai SPASI |

## Tips Akurasi

Kalau hasil baca kurang akurat, atur ambang deteksi di bagian **KONFIGURASI**:

- `FILL_MIN` — minimal "tinta" agar sel dianggap terisi.
- `WINNER_GAP` — selisih minimal pemenang vs pesaing sebelum dianggap `RAGU`.
- `CELL_SHRINK` — seberapa banyak tepi sel dipotong agar tidak kena garis grid.

Pencahayaan rata dan lembar yang nggak terlalu miring sangat membantu.

## Kontribusi

Kontribusi sangat diterima! Silakan buka *issue* atau kirim *pull request*. Beberapa ide pengembangan: dukungan jumlah soal/grid yang fleksibel lewat argumen, ekspor hasil ke CSV/Excel, dan koreksi batch banyak foto sekaligus.

## Lisensi

Proyek ini dirilis di bawah [MIT License](LICENSE). Bebas dipakai, dimodifikasi, dan didistribusikan.
