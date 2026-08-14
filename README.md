# CTF Agent — Sentul Labs Local Edition

CTF Agent adalah solver Capture The Flag berbasis AI yang menjalankan analisis di dalam Docker sandbox. Versi ini menambahkan GUI Windows, pilihan model bertingkat, provider Claude/Groq/Gemini, workspace persisten, trace yang dapat dipantau, dan generator write-up otomatis.

Proyek ini dikembangkan dari [verialabs/ctf-agent](https://github.com/verialabs/ctf-agent). Gunakan hanya pada kompetisi, challenge, dan target yang memang Anda berwenang uji.

## Fitur

- GUI desktop untuk membuat dan menjalankan satu challenge tanpa PowerShell.
- Model bertingkat **Hemat**, **Sedang**, dan **Kuat**.
- Codex GPT-5.6 melalui login Codex CLI.
- Claude melalui Anthropic API.
- Gemini terbaru melalui Gemini Developer API.
- GPT-OSS dan Llama melalui Groq API.
- Docker sandbox dengan tool pwn, reverse engineering, crypto, forensics, stego, dan web.
- Workspace persisten untuk `solve.py`, exploit, hasil decode, dan catatan.
- Trace perintah dan hasil agent yang dapat dipantau langsung.
- Redaksi otomatis untuk API key, token, PIN, cookie, password, dan header Authorization.
- Pembuatan `WRITEUP.md` otomatis setelah flag ditemukan.
- Mode manual-submit sebagai default: GUI dan CLI tidak mengirim flag ke platform kecuali CLI dijalankan secara eksplisit dengan `--submit`.

## Struktur Direktori

```text
CTF-Agent/
├── backend/                  # Solver, provider model, sandbox, trace, write-up
├── frontend/
│   ├── gui.pyw              # GUI Tkinter
│   └── README.md
├── sandbox/                 # Dockerfile sandbox CTF
├── challenges/              # Data challenge lokal (diabaikan Git)
├── logs/                    # Trace runtime (diabaikan Git)
├── tests/
├── .env                     # Kredensial lokal (diabaikan Git)
├── Start CTF Agent.cmd      # Launcher GUI Windows
└── run-local.ps1            # Launcher CLI satu challenge
```

## Persyaratan

- Windows 10/11.
- Python 3.14 atau lebih baru.
- Docker Desktop dengan Linux containers aktif.
- Codex CLI untuk model GPT-5.6, atau API key Anthropic/Groq/Gemini.
- RAM yang cukup untuk Docker sandbox; 8 GB minimum, 16 GB direkomendasikan.

## Instalasi

```powershell
git clone https://github.com/Sentul-Labs-ID/CTF-Agent.git
cd CTF-Agent

python -m pip install --user uv
python -m uv sync

docker build -f sandbox/Dockerfile.sandbox -t ctf-sandbox .
```

Untuk menggunakan GPT-5.6 melalui akun Codex:

```powershell
codex login
```

Salin konfigurasi awal jika `.env` belum tersedia:

```powershell
Copy-Item .env.example .env
```

Jangan commit atau membagikan file `.env`.

## Menjalankan GUI

Klik dua kali:

```text
Start CTF Agent.cmd
```

Alur penggunaan:

1. Klik **Buat Baru…** dan masukkan nama challenge.
2. Pilih kategori: web, pwn, reverse, crypto, forensics, misc, atau osint.
3. Salin deskripsi dan hint challenge secara lengkap.
4. Masukkan target spesifik pada **URL / host:port**:
   - Web: `https://target.example/challenge`
   - TCP: `nc target.example 1337`
5. Klik **Tambah File…** jika tersedia binary, source, PCAP, gambar, atau arsip.
6. Klik **Simpan Metadata**.
7. Pilih satu model.
8. Klik **Mulai Solver**.
9. Pantau tab **Output Solver** dan **Langkah Agent**.
10. Setelah flag ditemukan, periksa dan edit tab **Write-up**, lalu submit flag sendiri ke platform CTF.

Satu folder challenge digunakan untuk satu soal. Untuk platform non-CTFd atau situs khusus, masukkan setiap soal secara manual. Jangan menggunakan URL halaman daftar challenge sebagai target exploit; masukkan URL/host milik soal yang sedang dikerjakan.

## Pilihan Model

| Tingkat | Codex | Claude API | Groq API | Gemini API |
|---|---|---|---|---|
| **Hemat** | GPT-5.6 Luna | Claude Haiku 4.5 | GPT-OSS 20B | Gemini 3.5 Flash-Lite (GA) |
| **Sedang** | GPT-5.6 Terra | Claude Sonnet 4.6 | Llama 3.3 70B | Gemini 3.6 Flash (GA) |
| **Kuat** | GPT-5.6 Sol | Claude Opus 4.8 | GPT-OSS 120B | Gemini 3.1 Pro Preview |

- **Hemat** cocok untuk enumerasi awal dan challenge sederhana.
- **Sedang** adalah pilihan default untuk keseimbangan kemampuan, kecepatan, dan biaya.
- **Kuat** ditujukan untuk challenge sulit dan dapat memakai lebih banyak token atau biaya.

GUI menjalankan satu model per challenge untuk membantu mengendalikan pemakaian token.

## Konfigurasi API

API key dapat dimasukkan dari tombol **Atur API Key…** pada GUI. Nilainya disimpan lokal di `.env` dan tidak diteruskan melalui command line.

Konfigurasi manual:

```env
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=your_gemini_api_key_here
```

- Model Codex tidak memakai kedua key tersebut; Codex menggunakan sesi `codex login`.
- Claude menggunakan saldo dan rate limit Anthropic API.
- Groq menggunakan saldo dan rate limit akun Groq.
- Gemini menggunakan Gemini Developer API. Model Kuat (`gemini-3.1-pro-preview`) tidak tersedia pada free tier dan dapat memerlukan billing aktif.
- Integrasi Claude tidak memakai login atau kuota subscription Claude Code. Anthropic melarang aplikasi pihak ketiga menawarkan login `claude.ai` atau rate limit subscription tanpa persetujuan sebelumnya.
- Output setiap putaran Groq dibatasi 4.096 token agar permintaan awal tidak langsung melampaui batas TPM akun on-demand. Riwayat dan beberapa putaran cepat masih dapat menyentuh rate limit; tunggu sebentar lalu lanjutkan jika Groq mengembalikan 429.
- Atur spending limit pada dashboard provider sebelum menjalankan challenge panjang.

## Hasil dan Artefak

Untuk challenge bernama `demo`, hasil tersimpan sebagai berikut:

```text
challenges/demo/
├── metadata.yml
├── distfiles/
├── workspace/
│   └── <model>/             # solve.py, exploit, notes, hasil decode
├── writeups/
│   └── <model>.md           # arsip write-up per model
└── WRITEUP.md               # write-up terbaru yang dapat diedit dari GUI
```

Trace JSONL berada di folder `logs/`. Redaksi kredensial bersifat best-effort; selalu periksa `WRITEUP.md` dan trace sebelum dipublikasikan.

## Menjalankan dari PowerShell

```powershell
.\run-local.ps1 -Challenge challenges\nama-challenge
```

Memilih model lain:

```powershell
.\run-local.ps1 `
  -Challenge challenges\nama-challenge `
  -Model codex/gpt-5.6-sol
```

Atau gunakan CLI langsung:

```powershell
.\.venv\Scripts\ctf-solve.exe `
  --challenge challenges\nama-challenge `
  --models codex/gpt-5.6-terra `
  --no-submit `
  --max-challenges 1 `
  -v
```

## Tool Sandbox

| Kategori | Tool utama |
|---|---|
| Binary/Reverse | radare2, GDB, objdump, binwalk, strings, readelf, pyghidra |
| Pwn | pwntools, ROPgadget, angr, unicorn, capstone |
| Crypto | SageMath, RsaCtfTool, z3, gmpy2, pycryptodome, cado-nfs |
| Forensics | volatility3, Sleuthkit, foremost, exiftool |
| Stego | steghide, stegseek, zsteg, ImageMagick, tesseract |
| Web | curl, nmap, Python requests, Flask |
| Misc | ffmpeg, sox, Pillow, NumPy, SciPy, PyTorch |

## Pengujian

```powershell
.\.venv\Scripts\pytest.exe -q
.\.venv\Scripts\ruff.exe check backend frontend tests
```

## Keamanan

- Gunakan hanya pada target yang tercakup dalam aturan kompetisi.
- Jangan memasukkan PIN tim, cookie login, atau API key ke deskripsi challenge.
- GUI tidak melakukan submit flag otomatis.
- Docker mengisolasi tool solver, tetapi target jaringan tetap berasal dari input pengguna.
- Hentikan agent jika terlihat mengulang langkah atau pemakaian token meningkat tanpa kemajuan.

## Kredit

- [Veria Labs — ctf-agent](https://github.com/verialabs/ctf-agent), proyek upstream.
- [es3n1n/Eruditus](https://github.com/es3n1n/Eruditus), helper interaksi CTFd dan HTML pada upstream.

## Lisensi

Repositori menggunakan struktur dual-license:

- Material dan perubahan milik Sentul Labs menggunakan [Sentul Labs CDE License v1.0](LICENSES/SENTUL-CDE-1.0.txt). Lisensi ini mengizinkan penggunaan komersial, modifikasi, redistribusi, dan sublicensing dengan kewajiban atribusi.
- Material upstream Veria Labs tetap menggunakan [MIT License](LICENSES/MIT-Veria-Labs.txt).
- Pembagian dan atribusi lengkap tersedia pada [LICENSE](LICENSE), [NOTICE.md](NOTICE.md), dan [peta lisensi](LICENSES/README.md).

Lisensi khusus ini tidak mencabut hak yang sudah diberikan pada versi historis yang sebelumnya dirilis di bawah MIT.
