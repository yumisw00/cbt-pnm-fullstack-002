# Sistem CBT D3 TI PNM — Realisasi awal TA

Aplikasi web CBT berbasis FastAPI + SQLAlchemy dengan UI HTML/JS, REST API, database SQLite untuk uji lokal dan dukungan PostgreSQL melalui `DATABASE_URL`.

## Fitur yang sudah diimplementasikan
- Login JWT dan pembatasan akses berbasis peran: admin, dosen, pengawas, mahasiswa.
- Data awal demo, mata kuliah, pembuatan paket ujian dan token ruang.
- Soal pilihan ganda A–E dan esai, termasuk kunci referensi dan kata kunci wajib.
- Fisher–Yates Shuffle pada urutan soal serta urutan opsi pilihan ganda per sesi.
- Penyimpanan jawaban otomatis dan submit penilaian.
- Penilaian esai berbasis pra-pemrosesan Bahasa Indonesia (Sastrawi jika terpasang), TF-IDF, Cosine Similarity, dan cakupan kata kunci.
- Telemetri browser (tab tersembunyi, blur, fullscreen, klik kanan, salin/tempel), akumulasi penalti, penguncian saat melewati ambang dan fitur buka kembali oleh pengawas/dosen/admin.
- Dasbor pemantauan dan ekspor rekap nilai CSV.
- Endpoint detail penilaian esai dan override manual oleh dosen.

## Menjalankan di Linux / Windows
Disarankan Python 3.11 atau 3.12.

```bash
python -m venv .venv
# Linux:
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Buka `http://127.0.0.1:8000`. Dokumentasi API: `http://127.0.0.1:8000/docs`.
Database `cbt.db` dibuat otomatis saat startup.

## Akun demo
| Peran | Nomor induk | Kata sandi |
|---|---|---|
| Administrator | `admin` | `Admin123!` |
| Dosen | `dosen` | `Dosen123!` |
| Pengawas | `pengawas` | `Awasi123!` |
| Mahasiswa | `223307105` | `Mhs12345!` |

Buat paket ujian sebagai dosen dengan token misalnya `PNM26A`, tambahkan beberapa soal, lalu keluar dan masuk sebagai mahasiswa untuk memulai ujian menggunakan token tersebut.

## Menggunakan PostgreSQL
Buat database PostgreSQL dan set environment sebelum menjalankan aplikasi:

```bash
export DATABASE_URL='postgresql+psycopg://user:password@localhost:5432/cbt_pnm'
export JWT_SECRET='ganti-dengan-secret-acak-panjang'
uvicorn app.main:app --reload
```

Pada PowerShell gunakan `$env:DATABASE_URL=...` dan `$env:JWT_SECRET=...`.

## Endpoint inti
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/profile`
- `GET|POST /api/v1/courses`
- `GET|POST /api/v1/packets`
- `GET|POST /api/v1/packets/{id}/questions`
- `POST /api/v1/sessions/start`
- `GET /api/v1/sessions/{id}/paper`
- `PUT /api/v1/sessions/{id}/autosave`
- `POST /api/v1/sessions/{id}/submit`
- `POST /api/v1/proctoring/event`
- `GET /api/v1/proctoring/live/{packet_id}`
- `POST /api/v1/proctoring/unlock/{session_id}`
- `GET /api/v1/grading/essay-detail/{answer_id}`
- `PUT /api/v1/grading/manual-override/{answer_id}`
- `GET /api/v1/reports/packet/{packet_id}/export`

## Catatan batasan dan keamanan
1. Ini adalah implementasi MVP fungsional, bukan sistem produksi yang sudah diaudit keamanan atau diuji beban 100 pengguna.
2. Deteksi browser hanya telemetri indikatif dan dapat dipicu perpindahan fokus yang sah; tidak dapat menjamin semua kecurangan terdeteksi. Penguncian dan keputusan akademik perlu SOP serta tinjauan manusia.
3. Skor TF-IDF/cosine bukan pemahaman semantik. Dosen harus meninjau skor esai, terutama jawaban benar dengan redaksi berbeda.
4. Sebelum produksi, ganti `JWT_SECRET`, gunakan HTTPS, migrasi database formal (Alembic), tambahkan rate limit, audit log, backup, kebijakan privasi, manajemen akun, pengujian akses lintas peran, dan uji beban.
5. Akun demo dan kata sandi awal hanya untuk lokal; jangan deploy dengan kredensial ini.
