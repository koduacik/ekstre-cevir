#!/usr/bin/env python3
"""Tablo modu doğruluk testi — üretilen Excel'i HÜCRE HÜCRE beklenenle karşılaştırır.
Ayrıca: ekstre örnekleri hâlâ 'ekstre' modunda mı, sayı dönüştürücü doğru mu."""
from __future__ import annotations
import json, sys
from pathlib import Path
from openpyxl import load_workbook

BURADA = Path(__file__).parent
sys.path.insert(0, str(BURADA.parent))
from ekstre_cevir import BelgeOkunamadi, cevir, hucre_degeri  # noqa: E402

hatalar: list[str] = []

def esit(a, b):
    if isinstance(b, float) or isinstance(a, float):
        return isinstance(a, (int, float)) and isinstance(b, (int, float)) and abs(a - b) < 0.005
    return a == b and type(a) is type(b)

# 1) sayı dönüştürücü
for girdi, beklenen in [("1.234,56", 1234.56), ("120", 120), ("-3.254,65", -3254.65), ("1.234,56-", -1234.56),
                        ("1.250,00 TL", 1250.0), ("250 ₺", 250), ("0532", "0532"), ("007", "007"),
                        ("05.01.2025", "05.01.2025"), ("STK-1000", "STK-1000"), ("0", 0), ("0,50", 0.5),
                        ("Vida M6", "Vida M6"), ("1.840", 1840)]:
    sonuc = hucre_degeri(girdi)
    if not esit(sonuc, beklenen):
        hatalar.append(f"hucre_degeri({girdi!r}) = {sonuc!r}, beklenen {beklenen!r}")
print(f"sayı dönüştürücü : {14 - len(hatalar)}/14")

# 2) ekstreler hâlâ ekstre
for ad in "abc":
    _, mod, _ = cevir(BURADA / f"ornek_duzen_{ad}.pdf")
    (BURADA / f"ornek_duzen_{ad}_ekstre.xlsx").unlink(missing_ok=True)
    if mod != "ekstre":
        hatalar.append(f"ornek_duzen_{ad}: mod {mod}, beklenen ekstre")
print(f"ekstre tanıma    : {'3/3' if not any('ornek_duzen' in h for h in hatalar) else 'HATA'}")

# 3) tablolar hücre hücre
beklenen = json.loads((BURADA / "tablo" / "beklenen.json").read_text(encoding="utf-8"))
for ad, b in beklenen.items():
    pdf = BURADA / "tablo" / f"{ad}.pdf"
    if b is None:
        try:
            cevir(pdf); hatalar.append(f"{ad}: hata beklenirdi, dosya üretildi")
        except BelgeOkunamadi:
            print(f"{ad:16s} : doğru — tablo yok dedi")
        continue
    hedef, mod, _ = cevir(pdf)
    ws_listesi = load_workbook(hedef).worksheets
    hedef.unlink()
    once = len(hatalar)
    if mod != "tablo":
        hatalar.append(f"{ad}: mod {mod}, beklenen tablo")
    if len(ws_listesi) != 1:
        hatalar.append(f"{ad}: {len(ws_listesi)} sayfa, beklenen 1 (birleşmedi)")
    satirlar = [list(r) for r in ws_listesi[0].iter_rows(values_only=True)]
    if satirlar[0] != b["basliklar"]:
        hatalar.append(f"{ad}: başlık {satirlar[0]} ≠ {b['basliklar']}")
    veri = satirlar[1:]
    if len(veri) != len(b["satirlar"]):
        hatalar.append(f"{ad}: {len(veri)} satır ≠ {len(b['satirlar'])}")
    yanlis = 0
    for i, (o, e) in enumerate(zip(veri, b["satirlar"]), start=2):
        for j, (oh, eh) in enumerate(zip(o, e)):
            if not esit(oh, eh):
                yanlis += 1
                if yanlis <= 3:
                    hatalar.append(f"{ad}: satır {i} kolon {j+1}: {oh!r} ≠ {eh!r}")
    toplam = sum(len(r) for r in b["satirlar"])
    print(f"{ad:16s} : {toplam - yanlis}/{toplam} hücre doğru" + ("" if len(hatalar) == once else "  ✗"))

print()
for h in hatalar:
    print("  ·", h)
print("SONUÇ:", "TEMİZ" if not hatalar else f"{len(hatalar)} sorun")
sys.exit(1 if hatalar else 0)
