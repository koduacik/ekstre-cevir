#!/usr/bin/env python3
"""Test için sahte banka ekstresi PDF'leri üretir — üç farklı düzen.

Gerçek ekstre kullanmadan geliştirme yapmak için. Üç düzen bilerek farklı:
  duzen_a : klasik tablo, eksi işareti başta, "Tarih Açıklama Tutar Bakiye"
  duzen_b : eksi işareti SONDA (1.234,56-), açıklama iki satıra bölünüyor
  duzen_c : çizgisiz (boşlukla hizalı) tablo, borç/alacak ayrı kolonlarda
"""
from __future__ import annotations
import random
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

pdfmetrics.registerFont(TTFont("DejaVu", "/System/Library/Fonts/Supplemental/Arial.ttf"))
pdfmetrics.registerFont(TTFont("DejaVu-Bold", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"))

ACIKLAMALAR = [
    "MARKET ALISVERIS - BIM A.S.", "MAAS ODEMESI", "EFT GELEN - AHMET YILMAZ",
    "KREDI KARTI ODEMESI", "FATURA ODEME ELEKTRIK", "ATM NAKIT CEKIM",
    "HAVALE GIDEN - OZY YAZILIM LTD STI SIRKETI ODEME ACIKLAMASI UZUN",
    "POS HARCAMA - AKARYAKIT", "KIRA ODEMESI", "FAIZ TAHAKKUKU",
    "GSM FATURA ODEMESI", "SIGORTA PRIMI",
]

def isaretli(x: float) -> str:
    return ("-" if x < 0 else "") + tl(x)


def tl(x: float) -> str:
    s = f"{abs(x):,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")
    return s

def hareketler(n: int, tohum: int):
    rnd = random.Random(tohum)
    g = date(2025, 1, 3)
    bakiye = 12500.00
    out = []
    for _ in range(n):
        g += timedelta(days=rnd.randint(1, 6))
        tutar = round(rnd.uniform(45, 8500), 2)
        if rnd.random() < 0.65:
            tutar = -tutar
        bakiye = round(bakiye + tutar, 2)
        out.append((g.strftime("%d.%m.%Y"), rnd.choice(ACIKLAMALAR), tutar, bakiye))
    return out

def _basliklar(c, baslik, alt):
    c.setFont("DejaVu-Bold", 13); c.drawString(40, 800, baslik)
    c.setFont("DejaVu", 8); c.drawString(40, 786, alt)
    c.drawString(40, 774, "Hesap: TR00 0000 0000 0000 0000 0000 00   Sayfa dokumu")

def duzen_a(yol: Path, hrk):
    c = canvas.Canvas(str(yol), pagesize=A4); y = 740
    _basliklar(c, "HESAP HAREKETLERI", "ORNEK BANKASI A.S. - test amacli uretilmistir")
    c.setFont("DejaVu-Bold", 9)
    for x, t in ((40, "Tarih"), (110, "Aciklama"), (400, "Tutar"), (490, "Bakiye")):
        c.drawString(x, y, t)
    y -= 6; c.line(40, y, 555, y); y -= 14
    c.setFont("DejaVu", 8)
    for tarih, acik, tutar, bak in hrk:
        if y < 70:
            c.showPage(); y = 780; _basliklar(c, "HESAP HAREKETLERI (devam)", "ORNEK BANKASI A.S.")
            y = 740; c.setFont("DejaVu", 8)
        c.drawString(40, y, tarih); c.drawString(110, y, acik[:52])
        c.drawRightString(465, y, ("-" if tutar < 0 else "") + tl(tutar))
        c.drawRightString(555, y, isaretli(bak))
        y -= 13
    c.save()

def duzen_b(yol: Path, hrk):
    c = canvas.Canvas(str(yol), pagesize=A4); y = 740
    _basliklar(c, "HESAP EKSTRESI", "IKINCI BANKA - test amacli uretilmistir")
    c.setFont("DejaVu-Bold", 9)
    for x, t in ((40, "Islem Tarihi"), (130, "Islem Aciklamasi"), (400, "Islem Tutari"), (490, "Bakiye")):
        c.drawString(x, y, t)
    y -= 6; c.line(40, y, 555, y); y -= 14
    c.setFont("DejaVu", 8)
    for tarih, acik, tutar, bak in hrk:
        if y < 70:
            c.showPage(); y = 740; _basliklar(c, "HESAP EKSTRESI (devam)", "IKINCI BANKA")
            c.setFont("DejaVu", 8)
        c.drawString(40, y, tarih)
        # açıklama iki satıra bölünür
        c.drawString(130, y, acik[:28])
        c.drawRightString(465, y, tl(tutar) + ("-" if tutar < 0 else " "))
        c.drawRightString(555, y, tl(bak) + ("-" if bak < 0 else " "))
        if len(acik) > 28:
            y -= 10; c.drawString(130, y, acik[28:56])
        y -= 13
    c.save()

def duzen_c(yol: Path, hrk):
    c = canvas.Canvas(str(yol), pagesize=A4); y = 740
    _basliklar(c, "HESAP DOKUMU", "UCUNCU BANKA - test amacli uretilmistir")
    c.setFont("DejaVu-Bold", 9)
    for x, t in ((40, "TARIH"), (110, "ACIKLAMA"), (360, "BORC"), (440, "ALACAK"), (520, "BAKIYE")):
        c.drawString(x, y, t)
    y -= 16
    c.setFont("DejaVu", 8)
    c.drawString(40, y, "01.01.2025"); c.drawString(110, y, "DEVREDEN BAKIYE")
    c.drawRightString(555, y, tl(12500.00)); y -= 13
    for tarih, acik, tutar, bak in hrk:
        if y < 70:
            c.showPage(); y = 740; _basliklar(c, "HESAP DOKUMU (devam)", "UCUNCU BANKA")
            c.setFont("DejaVu", 8)
        c.drawString(40, y, tarih); c.drawString(110, y, acik[:46])
        if tutar < 0: c.drawRightString(420, y, tl(tutar))
        else:         c.drawRightString(500, y, tl(tutar))
        c.drawRightString(570, y, isaretli(bak))
        y -= 13
    c.save()

def csv_yaz(yol: Path, hrk):
    with open(yol, "w", encoding="utf-8") as f:
        f.write("tarih;aciklama;tutar;bakiye\n")
        for tarih, acik, tutar, bak in hrk:
            f.write(f"{tarih};{acik};{tutar:.2f};{bak:.2f}\n")


if __name__ == "__main__":
    burada = Path(__file__).parent
    for ad, fn, (n, tohum) in (("a", duzen_a, (46, 1)), ("b", duzen_b, (38, 2)), ("c", duzen_c, (52, 3))):
        hrk = hareketler(n, tohum)
        fn(burada / f"ornek_duzen_{ad}.pdf", hrk)
        csv_yaz(burada / f"gercek_{ad}.csv", hrk)
    for p in sorted(burada.glob("ornek_*.pdf")):
        print(f"  {p.name}  {p.stat().st_size//1024} KB")
