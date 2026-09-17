# OMR Scanner — Koreksi Otomatis Lembar Jawaban Pilihan Ganda

Tool sederhana untuk **koreksi otomatis lembar jawaban pilihan ganda (OMR / bubble sheet)** pakai Python + OpenCV. Bisa baca dari **foto/scan** atau langsung dari **webcam (live)**. Logika pembacaan grid sama persis antara mode foto dan webcam — bedanya cuma sumber input.

Cocok buat guru/pengajar yang mau koreksi ulangan cepet tanpa scanner khusus.

---

## Fitur

- **Mode Webcam** — arahkan lembar ke kamera, otomatis terkoreksi begitu terbaca stabil.
- **Mode Foto** — koreksi dari file gambar (`.jpg`, `.png`, dll).
- **Mode HP Android** — pakai kamera HP yang jauh lebih jernih dari webcam laptop, tersedia dua cara (lihat bagian [Windows & Android](#-windows--android--kamera-hp)).
- Deteksi grid otomatis (perspective warp), jadi lembar nggak harus lurus sempurna.
- Mendukung **2 blok grid** (soal 1–30 dan 31–60).
- Deteksi status jawaban: `BENAR`, `SALAH`, `KOSONG`, dan `RAGU` (kalau ada dua tanda yang sama-sama kuat).
- **Gambar verifikasi** otomatis (hijau = benar, merah = salah/kosong, oranye = ragu) supaya bisa dicek manual.
- Skor otomatis dari kunci jawaban CSV.

---

## Format Lembar Jawaban

Default konfigurasi:

| Parameter | Nilai | Keterangan |
|-----------|-------|------------|
| Opsi | A–E | 5 pilihan per soal |
| Soal per grid | 30 | |
| Jumlah grid | 2 | total 60 soal |

Kalau format lembarmu beda, ubah konstanta di bagian **KONFIGURASI** di dalam script.

---

## Persyaratan

**Mode foto & webcam (`run.py`):**
- Python 3.7+
- OpenCV (`opencv-python`)
- NumPy

**Mode HP Android (`ip_webcam.py` & `app.py`):** tambahan
- Flask (`flask`)
- PyOpenSSL (`pyopenssl`) — untuk HTTPS otomatis
- pyngrok (`pyngrok`) — **opsional**, hanya kalau pakai metode ngrok

---

## Instalasi

```bash
git clone https://github.com/restugbk/omr-scanner.git
cd omr-scanner
pip install opencv-python numpy
```

Untuk fitur HP Android, install tambahan:

```bash
pip install flask pyopenssl
```

---

## Cara Pakai

### Mode Webcam (default)

Nggak kasih file gambar → langsung buka kamera:

```bash
python run.py -k kunci_jawaban.csv
```

Di mode webcam:
- Arahkan lembar jawaban ke kamera (usahakan 2 grid kelihatan penuh & rata).
- Begitu terbaca stabil → **otomatis** dikoreksi.
- `[SPASI]` → koreksi manual kapan saja.
- `[Q]` / `[ESC]` → keluar.

### Mode Foto

Kasih file gambarnya:

```bash
python run.py lembar.jpg -k kunci_jawaban.csv
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

---

## 📱 Windows & Android — Kamera HP

Webcam bawaan laptop sering kualitasnya kurang bagus untuk scan lembar jawaban. Dua script berikut memungkinkan kamu pakai **kamera HP Android** yang jauh lebih tajam.

> **Catatan:** `run.py` yang asli tidak diubah sama sekali — tetap bisa dipakai seperti biasa. Dua script di bawah hanya *tambahan*.

---

### Opsi A — IP Webcam (`ip_webcam.py`)
**HP jadi webcam via WiFi, hasil tampil di window OpenCV di PC.**

**Langkah:**

1. Install app **[IP Webcam](https://play.google.com/store/apps/details?id=com.pas.webcam)** di Android (gratis).
2. Buka app → gulir ke bawah → tap **"Start server"**.
3. Catat URL yang muncul, contoh: `http://192.168.1.5:8080`.
4. Di app IP Webcam: **Settings → Video preferences → Resolution → 720p**
   (lebih rendah = lebih smooth, 1080p sering lag di WiFi 2.4GHz).
5. Pastikan HP & PC terhubung ke **WiFi yang sama**.
6. Jalankan:

```bash
python ip_webcam.py http://192.168.1.5:8080 -k kunci_jawaban.csv
```

Script ini pakai **background thread** untuk terus-menerus drain buffer kamera, sehingga delay jauh lebih kecil dibanding buka stream URL langsung.

**Kontrol sama seperti mode webcam biasa:** `[SPASI]` jepret, `[Q]` keluar.

---

### Opsi B — Web Scanner (`app.py`)
**HP jadi scanner langsung lewat browser — tidak perlu install apapun di HP.**

Server Flask berjalan di PC, HP Android membuka halaman web lalu mengirim foto ke PC untuk diproses. Tampilannya mobile-friendly dengan dark mode, auto-scan, dan overlay verifikasi langsung di layar HP.

**Langkah awal (sama untuk semua metode):**

```bash
python app.py -k kunci_jawaban.csv
```

Lalu pilih **salah satu** cara di bawah untuk buka di HP:

---

#### Metode 1 — HTTP + Chrome flag *(paling simpel, tanpa internet)*

```bash
python app.py --http -k kunci_jawaban.csv
```

Di HP Android (Chrome):
1. Buka `chrome://flags/#unsafely-treat-insecure-origin-as-secure`
2. Tambahkan `http://IP_PC:8765` di kolom yang muncul
3. Tap **"Relaunch"**
4. Buka `http://IP_PC:8765`

> IP PC tertera di terminal saat `app.py` dijalankan.

---

#### Metode 2 — ngrok HTTPS *(paling mudah, butuh internet sebentar)*

```bash
pip install pyngrok
python app.py --ngrok -k kunci_jawaban.csv
```

Terminal akan cetak URL `https://xxxx.ngrok-free.app` — buka di Chrome Android, kamera langsung aktif tanpa peringatan apapun.

---

#### Metode 3 — HTTPS self-signed *(tanpa internet, tanpa Chrome flag)*

```bash
python app.py -k kunci_jawaban.csv   # tanpa flag apapun
```

Buka URL `https://IP_PC:8765` di Chrome Android. Kalau muncul peringatan:
tap **"Lanjutan"** → **"Lanjutkan ke IP (tidak aman)"**

> Jika tombol "Lanjutan" tidak muncul, pakai Metode 1 atau 2.

---

#### Kalau URL tidak bisa dibuka sama sekali

Kemungkinan Windows Firewall memblokir port. Jalankan perintah ini di **Command Prompt (Run as Administrator)**:

```cmd
netsh advfirewall firewall add rule name="OMR Scanner" dir=in action=allow protocol=TCP localport=8765
```

Atau: **Windows Defender Firewall → Allow an app → Add Python**.

---

## Opsi Command Line

### `run.py` (original)

| Argumen | Default | Keterangan |
|---------|---------|------------|
| `image` | — | (opsional) file foto/scan. Kosong → buka webcam |
| `-k`, `--key` | — | file kunci jawaban CSV |
| `-o`, `--overlay` | `verifikasi.png` | nama file verifikasi (mode foto) |
| `--no-overlay` | — | jangan buat gambar verifikasi |
| `-c`, `--camera` | `0` | index kamera (coba 1/2 kalau gagal) |
| `--save-dir` | `hasil_scan` | folder simpan hasil mode webcam |
| `--manual` | — | webcam: matikan auto-jepret, hanya pakai SPASI |

### `ip_webcam.py`

| Argumen | Default | Keterangan |
|---------|---------|------------|
| `url` | — | URL server IP Webcam, contoh: `http://192.168.1.5:8080` |
| `-k`, `--key` | — | file kunci jawaban CSV |
| `--save-dir` | `hasil_scan` | folder simpan hasil |
| `--manual` | — | matikan auto-jepret |

### `app.py`

| Argumen | Default | Keterangan |
|---------|---------|------------|
| `-k`, `--key` | `kunci_jawaban.csv` | file kunci jawaban CSV |
| `-p`, `--port` | `8765` | port server |
| `--http` | — | HTTP biasa (kombinasikan dengan Chrome flag) |
| `--ngrok` | — | tunnel HTTPS via ngrok (butuh `pip install pyngrok`) |

---

## Tips Akurasi

Kalau hasil baca kurang akurat, atur ambang deteksi di bagian **KONFIGURASI**:

- `FILL_MIN` — minimal "tinta" agar sel dianggap terisi.
- `WINNER_GAP` — selisih minimal pemenang vs pesaing sebelum dianggap `RAGU`.
- `CELL_SHRINK` — seberapa banyak tepi sel dipotong agar tidak kena garis grid.

Pencahayaan rata dan lembar yang nggak terlalu miring sangat membantu.

Khusus mode HP: pakai **kamera belakang**, pastikan pencahayaan cukup, dan tahan HP di atas lembar dengan jarak ~30–40 cm.

---

## Kontribusi

Kontribusi sangat diterima! Silakan buka *issue* atau kirim *pull request*. Beberapa ide pengembangan: dukungan jumlah soal/grid yang fleksibel lewat argumen, ekspor hasil ke CSV/Excel, dan koreksi batch banyak foto sekaligus.

---

## Lisensi

Proyek ini dirilis di bawah [MIT License](LICENSE). Bebas dipakai, dimodifikasi, dan didistribusikan.
