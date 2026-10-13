# DrillAI — Fullscreen AI Desktop Automation for Windows

DrillAI adalah aplikasi baris perintah (*command-line interface*) Windows yang ringan dan efisien. Aplikasi ini menangkap tangkapan layar desktop (*fullscreen* atau *Region of Interest*), mendeteksi perubahan visual yang signifikan secara otomatis, lalu mengirimkan gambar ke Gemini AI melalui Google AI Studio API untuk menganalisis dan menjawab soal latihan, rumus matematika, diagram, dan tabel yang tampil di layar secara terstruktur.

---

## 1. Arsitektur Proyek

DrillAI dirancang secara modular dengan pemisahan tanggung jawab (*separation of concerns*):

```
drill-ai/
│
├── main.py                 # Titik masuk utama & CLI interface (argparse)
├── config.py               # Manajemen konfigurasi dan validasi boundary
├── screenshot.py           # Penangkapan layar fullscreen & ROI via mss (in-memory)
├── monitor_manager.py      # Enumerasi monitor dinamis & pemetaan koordinat
├── screen_detector.py      # Deteksi perubahan visual OpenCV, deduplikasi & cooldown
├── vision.py               # Utilitas kualitas gambar dan estimasi ROI
├── gemini_client.py        # Klien Gemini API resmi (google-genai) dengan retry
├── solver.py               # AI question solver & validasi skema JSON terstruktur
├── mouse_controller.py     # Kontrol kursor mouse aman untuk halaman latihan lokal
├── storage.py              # Penyimpanan riwayat analisis berbasis SQLite
├── logger.py               # Logging rotasi file & redaksi kunci rahasia
├── drillai.spec            # Konfigurasi pengemasan PyInstaller
├── requirements.txt        # Daftar dependensi Python
├── .env.example            # Template variabel lingkungan
├── .gitignore              # Pengecualian berkas rahasia & build
├── README.md               # Dokumentasi lengkap (Bahasa Indonesia)
│
├── tests/                  # Test suite otomatis (pytest)
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_screenshot.py
│   ├── test_monitor_manager.py
│   ├── test_screen_detector.py
│   ├── test_gemini_client.py
│   ├── test_solver.py
│   ├── test_mouse_controller.py
│   └── test_storage.py
│
├── fixtures/
│   └── local_practice_page/
│       └── index.html      # Halaman uji coba lokal interaktif (5 soal tes)
├── logs/                   # Direktori berkas log berotasi
└── results/                # Direktori database SQLite (drillai.db)
```

---

## 2. Fitur Utama

- **Fullscreen & Multi-Monitor Support**: Mendeteksi semua layar yang terhubung secara dinamis. Mendukung monitor utama (indeks 1), monitor kedua/ketiga (indeks 2+), atau seluruh gabungan virtual desktop (indeks 0).
- **Region of Interest (ROI)**: Opsi untuk membatasi pemindaian hanya pada area tertentu layar (`X,Y,WIDTH,HEIGHT`) guna menghemat bandwidth dan fokus pada kotak soal.
- **Deteksi Perubahan Visual Cerdas**: Menggunakan OpenCV dengan perbandingan frame, Gaussian blur normalization, perceptual hashing (MD5 downscale), debouncing, serta API cooldown untuk mencegah panggilan API yang berulang atau tidak perlu.
- **Analisis Multimodal Gemini**: Menganalisis teks bahasa Indonesia & bahasa Inggris, persamaan matematika (eksponen, akar, logaritma), tabel, diagram, dan pilihan ganda.
- **Respon Terstruktur & Tervalidasi**: Menghasilkan format JSON ketat dengan deteksi soal, opsi jawaban (A-E), jawaban yang diusulkan, penjelasan langkah demi langkah, dan tingkat keyakinan (*confidence*).
- **Keamanan & Perlindungan Data**: Kunci API tidak pernah dicetak di konsol atau disimpan dalam log/database (dilengkapi filter redaksi otomatis).
- **Pengendali Mouse Terbatas (Opt-in)**: Kontrol mouse dengan mode *dry-run* bawaan, batas kuota aksi maksimal, validasi batas layar, dan mekanisme *failsafe* darurat.
- **Penyimpanan SQLite**: Riwayat analisis disimpan secara otomatis tanpa menyimpan gambar mentah secara permanen kecuali diaktifkan.
- **Eksekusi Mandiri (Standalone Executable)**: Dapat dikompilasi menjadi `DrillAI.exe` dengan PyInstaller.

---

## 3. Persyaratan Sistem

- **Sistem Operasi**: Windows 10 atau Windows 11 (64-bit).
- **Python**: Python 3.9, 3.10, 3.11, atau 3.12 (Disarankan: Python 3.11).
- **Akses Internet**: Diperlukan untuk berkomunikasi dengan Google AI Studio API.
- **Kredensial**: Google Gemini API Key dari [Google AI Studio](https://aistudio.google.com/apikey).

---

## 4. Panduan Instalasi & Persiapan Lingkungan

Buka **Windows PowerShell** dan ikuti langkah-langkah berikut:

### Langkah 1: Kloning atau Buka Direktori Proyek
```powershell
cd C:\Users\Admin\drill-ai
```

### Langkah 2: Buat & Aktifkan Virtual Environment (Disarankan)
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
*(Catatan: Jika terjadi pembatasan eksekusi skrip di PowerShell, jalankan `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` terlebih dahulu).*

### Langkah 3: Pasang Dependensi
```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 5. Konfigurasi Lingkungan (`.env`)

Salin file `.env.example` menjadi `.env`:

```powershell
Copy-Item .env.example .env
```

Buka `.env` dan masukkan API Key Gemini Anda:
```env
GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxxxx
GEMINI_MODEL=gemini-2.0-flash
SCREENSHOT_INTERVAL=1.0
CHANGE_THRESHOLD=0.03
API_COOLDOWN=3.0
MONITOR_INDEX=1
REGION_ENABLED=false
REGION_X=0
REGION_Y=0
REGION_WIDTH=0
REGION_HEIGHT=0
MOUSE_ENABLED=false
MOUSE_DRY_RUN=true
MAX_MOUSE_ACTIONS=10
DEBUG=false
LOG_LEVEL=INFO
SAVE_SCREENSHOTS=false
AMBIGUOUS_IMAGE_POLICY=analyze
```

> **PENTING**: Jangan pernah membagikan atau mengunggah file `.env` ke Git repository publik. File `.env` sudah dimasukkan ke dalam `.gitignore`.

---

## 6. Panduan Perintah CLI (Command-Line Interface)

### 6.1 Memeriksa Lingkungan (`doctor`)
Periksa kesiapan dependensi, konfigurasi, direktori log/hasil, dan koneksi API:
```powershell
python main.py doctor
```
Untuk menguji konektivitas langsung ke Google Gemini API:
```powershell
python main.py doctor --test-api
```

### 6.2 Melihat Daftar Monitor (`monitors`)
Tampilkan semua layar yang terdeteksi beserta resolusi dan koordinatnya:
```powershell
python main.py monitors
```
*Output contoh:*
```
Available monitors:
  [0] Virtual Desktop: 3840x1080 at (0, 0)
  [1] Monitor 1 (Primary): 1920x1080 at (0, 0)
  [2] Monitor 2: 1920x1080 at (1920, 0)
```

### 6.3 Mengambil Pratinjau Tangkapan Layar (`preview`)
Uji tangkapan layar untuk memastikan monitor dan area ROI sudah sesuai sebelum menjalankan pemantauan:
```powershell
# Pratinjau monitor utama
python main.py preview

# Pratinjau monitor tertentu
python main.py preview --monitor 2

# Pratinjau dengan Region of Interest (ROI)
python main.py preview --region 200,150,1200,800 --output preview_roi.png
```

### 6.4 Memulai Pemantauan Desktop (`start`)

#### Mode Dry-Run (Tanpa Mengonsumsi Kuota API Gemini)
Uji deteksi perubahan visual desktop tanpa memanggil API:
```powershell
python main.py start --dry-run
```

#### Pemantauan Layar Penuh Normal (Primary Monitor)
```powershell
python main.py start
```

#### Pemantauan pada Monitor Tertentu
```powershell
python main.py start --monitor 2
```

#### Pemantauan dengan Region of Interest (ROI)
```powershell
python main.py start --region 200,150,1200,800 --interval 1.5 --threshold 0.04
```

#### Menghentikan Pemantauan
Tekan **`Ctrl + C`** di konsol. DrillAI akan menyelesaikan operasi yang sedang berjalan, merapikan memori, menyimpan ringkasan statistik, dan keluar dengan bersih (*graceful shutdown*).

### 6.5 Melihat Riwayat Analisis (`history`)
Tampilkan riwayat soal dan jawaban yang tersimpan di database lokal:
```powershell
python main.py history --limit 10
```

---

## 7. Cara Menentukan Koordinat Region of Interest (ROI)

Jika Anda hanya ingin menganalisis sebagian layar (misalnya hanya area jendela web browser yang menampilkan soal):

1. Format argumen: `--region X,Y,WIDTH,HEIGHT`
   - `X`: Titik piksel awal dari sisi kiri monitor (relatif terhadap monitor terpilih).
   - `Y`: Titik piksel awal dari sisi atas monitor.
   - `WIDTH`: Lebar area target (harus > 0).
   - `HEIGHT`: Tinggi area target (harus > 0).
2. Cara menentukan koordinat di Windows:
   - Ambil screenshot layar penuh dengan perintah `python main.py preview`.
   - Buka gambar di aplikasi seperti Paint atau Image Viewer.
   - Arahkan kursor ke sudut kiri-atas area soal untuk melihat koordinat `(X, Y)`.
   - Ukur lebar dan tinggi kotak soal tersebut `(WIDTH, HEIGHT)`.
   - Uji kembali dengan `python main.py preview --region X,Y,WIDTH,HEIGHT` hingga area yang tampil pas di kotak soal.

---

## 8. Halaman Latihan Lokal (Fixtures)

Tersedia halaman latihan mandiri yang dapat digunakan untuk menguji kemampuan tangkapan layar dan analisis soal:
- Lokasi berkas: `fixtures/local_practice_page/index.html`
- Buka berkas tersebut di Google Chrome atau Microsoft Edge:
```powershell
Start-Process "fixtures\local_practice_page\index.html"
```
Halaman ini memuat 5 pertanyaan (Matematika, IPA, dan Bahasa Indonesia) dengan tombol pilihan dan validasi skor.

---

## 9. Menjalankan Pengujian Otomatis (Testing)

Suite pengujian dirancang menggunakan `pytest` dan menggunakan teknik mocking penuh sehingga **tidak membutuhkan koneksi internet, tidak memakan kuota Gemini API, dan tidak menggerakkan mouse fisik**.

Jalankan seluruh test:
```powershell
pytest -v
```

Hasil uji coba mencakup:
- Validasi konfigurasi & boundary checks (`test_config.py`)
- Enumerasi & pemilihan monitor mss (`test_monitor_manager.py`)
- Pengambilan & kompresi tangkapan layar in-memory (`test_screenshot.py`)
- Algoritma pendeteksi perubahan visual & cooldown (`test_screen_detector.py`)
- Penanganan respon & error retry Gemini client (`test_gemini_client.py`)
- Validasi skema respon AI solver (`test_solver.py`)
- Keselamatan dan dry-run mouse controller (`test_mouse_controller.py`)
- Penyimpanan dan pembacaan database SQLite (`test_storage.py`)

---

## 10. Pengemasan Executable Windows (PyInstaller)

Untuk membuat file executable tunggal `DrillAI.exe` yang dapat dijalankan tanpa instalasi Python:

```powershell
pyinstaller drillai.spec
```

Berkas hasil build akan berada di:
```
dist\DrillAI.exe
```

### Menguji Executable:
```powershell
.\dist\DrillAI.exe doctor
.\dist\DrillAI.exe monitors
.\dist\DrillAI.exe start --dry-run
```

> **Catatan Runtime Executable**: Letakkan berkas `.env` di direktori yang sama dengan `DrillAI.exe` agar konfigurasi dapat dibaca secara dinamis. Executable dibuat mandiri dan tidak menanamkan kunci rahasia ke dalam berkas biner.

---

## 11. Pertimbangan Keamanan & Etika

1. **Privasi Layar**: Tangkapan layar desktop dapat menangkap informasi pribadi, notifikasi obrolan, atau aplikasi latar belakang. Sangat disarankan untuk:
   - Menutup aplikasi pesan instan atau dokumen pribadi sebelum memulai pemantauan.
   - Menggunakan opsi `--region` agar hanya area soal yang dipantau.
2. **Kepatuhan & Integritas**: DrillAI dibuat untuk tujuan automasi latihan soal mandiri (*self-drill & learning automation*). Jangan gunakan alat ini untuk melanggar integritas akademik atau ketentuan ujian resmi pihak ketiga.
3. **Pengendali Mouse**: Pengendali mouse dinonaktifkan secara *default* (`MOUSE_ENABLED=false`) dan hanya berjalan dalam mode *dry-run* (`MOUSE_DRY_RUN=true`). Fitur *emergency failsafe* aktif di mana Anda cukup mengarahkan kursor ke pojok layar untuk membatalkan operasi mouse seketika.

---

## 12. Penyelesaian Masalah (Troubleshooting)

- **Error: `GEMINI_API_KEY is not set`**  
  *Solusi*: Pastikan berkas `.env` ada di folder proyek atau setel variabel lingkungan dengan `$env:GEMINI_API_KEY="kunci_anda"` di PowerShell.
- **Error: `429 Resource Exhausted / Quota Exceeded`**  
  *Solusi*: Periksa sisa kuota gratis Anda di Google AI Studio. Anda juga dapat memperbesar nilai `API_COOLDOWN` (misalnya menjadi `5.0` atau `10.0` detik) dan menaikkan `CHANGE_THRESHOLD` agar permintaan API lebih hemat.
- **Deteksi perubahan terlalu sensitif (misal karena kursor berkedip)**  
  *Solusi*: Naikkan nilai threshold, contoh: `--threshold 0.06`.
- **Tampilan monitor tidak sesuai resolusi sebenarnya**  
  *Solusi*: Windows Display Scaling (misal 125% atau 150%) dapat memengaruhi koordinat piksel. Jalankan `python main.py preview` untuk memverifikasi tangkapan layar aktual.

---

## 13. Lisensi

Hak Cipta (c) 2026 Tim Pengembang DrillAI. Dilindungi undang-undang.
