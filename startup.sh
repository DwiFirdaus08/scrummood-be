#!/bin/sh

# Memberi tahu shell untuk berhenti jika ada perintah yang gagal
set -e

# Menjalankan migrasi database menggunakan perintah flask
# Ini seringkali lebih andal daripada menjalankan skrip python secara langsung
echo "==> [STARTUP] Menjalankan migrasi database dengan 'flask db upgrade'..."
flask db upgrade

echo "==> [STARTUP] Migrasi database selesai."

# Setelah migrasi berhasil, baru jalankan server aplikasi utama
echo "==> [STARTUP] Memulai server Gunicorn..."
exec gunicorn app:app