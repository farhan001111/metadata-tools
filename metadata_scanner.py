#!/usr/bin/env python3
"""
metadata_scanner.py - Metadata Leak Scanner

Audit metadata tersembunyi di file (gambar, PDF, DOCX) sebelum kamu publish/kirim
ke orang lain. Berguna buat cek kebocoran info: nama penulis, software yang dipakai,
lokasi GPS di foto, histori edit dokumen, dll.

Didukung:
  - Gambar: JPG, PNG, TIFF, dll (EXIF via Pillow, termasuk GPS)
  - PDF    : info dictionary (Author, Producer, CreationDate, dll) - parser manual
  - DOCX   : core.xml & app.xml (Author, Last Modified By, Company, dll)

Pemakaian:
  python3 metadata_scanner.py scan file1.jpg file2.pdf file3.docx
  python3 metadata_scanner.py scan ./folder_dokumen/ --recursive
  python3 metadata_scanner.py scan ./folder/ -o report.json

Hanya untuk file milikmu sendiri atau yang kamu punya izin audit.
"""

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

YELLOW, CYAN, RED, GREEN, GREY, RESET = (
    "\033[93m", "\033[96m", "\033[91m", "\033[92m", "\033[90m", "\033[0m"
)

BANNER = r"""
 ███╗   ███╗███████╗████████╗ █████╗ ██████╗  █████╗ ████████╗ █████╗
 ████╗ ████║██╔════╝╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗╚══██╔══╝██╔══██╗
 ██╔████╔██║█████╗     ██║   ███████║██║  ██║███████║   ██║   ███████║
 ██║╚██╔╝██║██╔══╝     ██║   ██╔══██║██║  ██║██╔══██║   ██║   ██╔══██║
 ██║ ╚═╝ ██║███████╗   ██║   ██║  ██║██████╔╝██║  ██║   ██║   ██║  ██║
 ╚═╝     ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝
                           V 1
"""

# Field yang dianggap "sensitif" kalau bocor ke publik
SENSITIVE_KEYS = {
    "author", "creator", "artist", "lastmodifiedby", "company", "manager",
    "gpsinfo", "gps_latitude", "gps_longitude", "producer",
    "make", "model", "software", "owner",
}


def print_banner():
    print(YELLOW + BANNER + RESET)
    print(f"{CYAN}   Metadata Leak Scanner v1.0  |  image / pdf / docx  |  audit your own files{RESET}")
    print(f"{GREY}   " + "-" * 72 + f"{RESET}\n")


def flag(key: str) -> bool:
    return key.lower().replace(" ", "").replace("_", "") in SENSITIVE_KEYS


# ---------- Image (EXIF) ----------
def scan_image(path: Path) -> dict:
    if not HAS_PIL:
        return {"error": "Pillow tidak terpasang"}
    result = {}
    try:
        img = Image.open(path)
        exif = img.getexif()
        if not exif:
            return {"info": "tidak ada metadata EXIF"}
        for tag_id, value in exif.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "GPSInfo":
                gps = {GPSTAGS.get(t, t): v for t, v in value.items()}
                result["GPSInfo"] = gps
            else:
                result[str(tag)] = str(value)[:200]
    except Exception as e:
        return {"error": str(e)}
    return result


# ---------- PDF (manual parse info dict) ----------
def scan_pdf(path: Path) -> dict:
    result = {}
    try:
        data = path.read_bytes()
        # cari /Info dictionary sederhana lewat regex (bukan parser PDF penuh,
        # tapi cukup untuk ambil metadata umum yang disimpan sebagai plain text)
        pattern = re.compile(
            rb"/(Author|Creator|Producer|Title|Subject|Keywords|CreationDate|ModDate)\s*\(([^)]*)\)"
        )
        for m in pattern.finditer(data):
            key = m.group(1).decode(errors="replace")
            val = m.group(2).decode(errors="replace").strip()
            if val:
                result[key] = val
        # cek XMP metadata (sering berisi info lebih detail / software asli)
        if b"<x:xmpmeta" in data:
            result["_note"] = "Ada blok XMP metadata tambahan (cek manual dgn 'strings file.pdf | grep xmp')"
        if not result:
            result["info"] = "tidak ada info dictionary standar ditemukan"
    except Exception as e:
        return {"error": str(e)}
    return result


# ---------- DOCX (core.xml + app.xml) ----------
NS = {
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
    "ep": "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties",
}


def scan_docx(path: Path) -> dict:
    result = {}
    try:
        with zipfile.ZipFile(path) as z:
            if "docProps/core.xml" in z.namelist():
                root = ET.fromstring(z.read("docProps/core.xml"))
                for child in root:
                    tag = child.tag.split("}")[-1]
                    if child.text:
                        result[tag] = child.text
            if "docProps/app.xml" in z.namelist():
                root = ET.fromstring(z.read("docProps/app.xml"))
                for child in root:
                    tag = child.tag.split("}")[-1]
                    if child.text:
                        result[tag] = child.text
    except Exception as e:
        return {"error": str(e)}
    if not result:
        result["info"] = "tidak ada docProps ditemukan"
    return result


IMAGE_EXT = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"}
EXT_MAP = {".pdf": scan_pdf, ".docx": scan_docx}


def scan_file(path: Path) -> dict:
    ext = path.suffix.lower()
    if ext in IMAGE_EXT:
        data = scan_image(path)
    elif ext in EXT_MAP:
        data = EXT_MAP[ext](path)
    else:
        return None
    return data


def collect_files(targets, recursive):
    files = []
    for t in targets:
        p = Path(t)
        if p.is_dir():
            glob = p.rglob("*") if recursive else p.glob("*")
            files.extend(f for f in glob if f.is_file())
        elif p.is_file():
            files.append(p)
        else:
            print(f"{RED}[!] Tidak ditemukan: {t}{RESET}")
    return files


def run_scan(targets, recursive, output):
    print_banner()
    files = collect_files(targets, recursive)
    supported = [f for f in files if f.suffix.lower() in IMAGE_EXT | set(EXT_MAP.keys())]

    if not supported:
        print("Tidak ada file yang didukung (jpg/png/pdf/docx) ditemukan.")
        return

    report = []
    for f in supported:
        meta = scan_file(f)
        if meta is None:
            continue
        sensitive_hits = {k: v for k, v in meta.items() if flag(k)}
        entry = {"file": str(f), "metadata": meta, "sensitive_fields": sensitive_hits}
        report.append(entry)

        print(f"{CYAN}[+] {f}{RESET}")
        if "error" in meta:
            print(f"    {RED}error: {meta['error']}{RESET}")
        elif "info" in meta:
            print(f"    {GREY}{meta['info']}{RESET}")
        else:
            for k, v in meta.items():
                marker = f"{RED}⚠{RESET}" if flag(k) else " "
                print(f"    {marker} {k}: {v}")
        print()

    total_sensitive = sum(1 for r in report if r["sensitive_fields"])
    print(f"{GREEN}Selesai.{RESET} {len(report)} file dianalisis, "
          f"{RED if total_sensitive else GREEN}{total_sensitive} file mengandung field sensitif{RESET}.")

    if output:
        Path(output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Laporan lengkap disimpan ke {output}")


def interactive_menu():
    print_banner()
    while True:
        print(f"{CYAN}Pilih opsi:{RESET}")
        print("  [1] Scan satu file")
        print("  [2] Scan folder (tidak rekursif)")
        print("  [3] Scan folder (rekursif, semua subfolder)")
        print("  [4] Lihat field yang dianggap sensitif")
        print("  [0] Keluar")
        choice = input(f"{GREY}>> {RESET}").strip()

        if choice == "1":
            target = input("Path file: ").strip()
            out = input("Simpan laporan JSON ke (kosongkan jika tidak perlu): ").strip()
            run_scan([target], recursive=False, output=out or None)
        elif choice == "2":
            target = input("Path folder: ").strip()
            out = input("Simpan laporan JSON ke (kosongkan jika tidak perlu): ").strip()
            run_scan([target], recursive=False, output=out or None)
        elif choice == "3":
            target = input("Path folder: ").strip()
            out = input("Simpan laporan JSON ke (kosongkan jika tidak perlu): ").strip()
            run_scan([target], recursive=True, output=out or None)
        elif choice == "4":
            print(f"\n{YELLOW}Field yang ditandai sensitif:{RESET}")
            for k in sorted(SENSITIVE_KEYS):
                print(f"  - {k}")
            print()
        elif choice == "0":
            print("Sampai jumpa.")
            break
        else:
            print(f"{RED}Pilihan tidak dikenal.{RESET}\n")


def main():
    p = argparse.ArgumentParser(description="Metadata Leak Scanner")
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("scan", help="scan TIDAK rekursif (hanya file di level atas folder)")
    s.add_argument("targets", nargs="+", help="file atau folder yang mau di-scan")
    s.add_argument("-o", "--output", help="simpan laporan lengkap ke file JSON")

    sr = sub.add_parser("scan-r", help="scan REKURSIF (termasuk semua subfolder di dalamnya)")
    sr.add_argument("targets", nargs="+", help="file atau folder yang mau di-scan")
    sr.add_argument("-o", "--output", help="simpan laporan lengkap ke file JSON")

    sub.add_parser("menu", help="buka menu interaktif")
    args = p.parse_args()

    if args.cmd == "scan":
        run_scan(args.targets, recursive=False, output=args.output)
    elif args.cmd == "scan-r":
        run_scan(args.targets, recursive=True, output=args.output)
    elif args.cmd == "menu" or args.cmd is None:
        interactive_menu()


if __name__ == "__main__":
    main()
