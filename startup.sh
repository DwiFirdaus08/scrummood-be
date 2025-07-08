#!/bin/sh

# Memberi tahu shell untuk berhenti jika ada perintah yang gagal
set -e

# Jalankan migrasi database terlebih dahulu
echo "Menjalankan migrasi database..."
python migrate.py
echo "Migrasi selesai."

# Setelah migrasi berhasil, baru jalankan server aplikasi
echo "Memulai server Gunicorn..."
exec gunicorn app:app