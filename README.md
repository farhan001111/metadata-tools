metadata-tools

Scanner metadata sederhana untuk mengaudit file gambar (JPG/PNG/dll), PDF, dan DOCX sebelum dibagikan ke publik. Tool ini membantu menemukan informasi tersembunyi di dalam file — seperti nama penulis, software yang dipakai, lokasi GPS, atau nama orang yang terakhir mengedit dokumen — yang seringkali tidak sengaja ikut terbawa saat file di-upload atau dikirim.


Fitur
Gambar: membaca metadata EXIF (Artist, Software, kamera, hingga koordinat GPS jika ada).
PDF: membaca info dictionary (Author, Producer, Creator, tanggal pembuatan).
DOCX: membaca docProps internal (penulis, nama perusahaan, waktu dibuat/diubah, histori revisi).
Menandai otomatis field yang dianggap sensitif dengan tanda ⚠.
Bisa scan satu file, satu folder, atau rekursif ke semua subfolder.
Bisa dipakai lewat argumen command line maupun menu interaktif.
Bisa ekspor laporan lengkap ke JSON.
Instalasi

Tool ini hanya butuh dua library tambahan (sisanya pakai Python standard library):

bash
pip install Pillow python-docx
Cara Pakai
1. Scan tidak rekursif (hanya file di level atas folder)
bash
python3 metadata_scanner.py scan file.jpg
python3 metadata_scanner.py scan ./folder_dokumen/
2. Scan rekursif (termasuk semua subfolder)
bash
python3 metadata_scanner.py scan-r ./folder_dokumen/
3. Simpan laporan lengkap ke JSON
bash
python3 metadata_scanner.py scan-r ./folder_dokumen/ -o report.json
4. Menu interaktif

Jalankan tanpa argumen untuk membuka menu pilihan:

bash
python3 metadata_scanner.py
Pilih opsi:
  [1] Scan satu file
  [2] Scan folder (tidak rekursif)
  [3] Scan folder (rekursif, semua subfolder)
  [4] Lihat field yang dianggap sensitif
  [0] Keluar
Contoh Output
[+] foto_test.jpg
    ⚠ Software: GIMP 2.10
    ⚠ Artist: Jane Doe

[+] dokumen_test.docx
    ⚠ creator: Budi Santoso
      Application: Microsoft Word
      created: 2024-01-10T09:15:00Z

Selesai. 2 file dianalisis, 2 file mengandung field sensitif.
