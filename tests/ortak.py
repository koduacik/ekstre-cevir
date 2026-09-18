"""Test belgesi üreticilerinin ortak yardımcıları.

Buradaki sayı biçimlendirme programdan bağımsız yazıldı; beklenen değerler
programın kendi fonksiyonlarıyla üretilmez.
"""
import csv
import os
from decimal import Decimal

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

GOVDE, KALIN = "Govde", "Kalin"

# Türkçe harfleri (ğ, ş, ı, İ) içeren yazı tipleri
_FONT_ADAYLARI = [
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ("/Library/Fonts/Arial Unicode.ttf", None),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]


def fontlari_kaydet():
    if GOVDE in pdfmetrics.getRegisteredFontNames():
        return
    for normal, kalin in _FONT_ADAYLARI:
        if os.path.exists(normal):
            pdfmetrics.registerFont(TTFont(GOVDE, normal))
            pdfmetrics.registerFont(TTFont(KALIN, kalin if kalin and os.path.exists(kalin) else normal))
            from reportlab.pdfbase.pdfmetrics import registerFontFamily
            registerFontFamily(GOVDE, normal=GOVDE, bold=KALIN)
            return
    raise RuntimeError("Türkçe karakterli bir TTF yazı tipi bulunamadı (Arial ya da DejaVuSans gerekli).")


def genislik(metin, font=GOVDE, boyut=8.5):
    return pdfmetrics.stringWidth(metin, font, boyut)


def tr(d, eksi="basta"):
    """Decimal → Türk biçimi. eksi: 'basta' → -1.234,56 · 'sonda' → 1.234,56- · None → işaretsiz."""
    d = Decimal(d)
    govde = "{:,.2f}".format(abs(d)).replace(",", "_").replace(".", ",").replace("_", ".")
    if d < 0 and eksi == "basta":
        return "-" + govde
    if d < 0 and eksi == "sonda":
        return govde + "-"
    return govde


def kanonik(d):
    return "{:.2f}".format(Decimal(d))


def kes(metin, en_fazla, font=GOVDE, boyut=8.5):
    """Genişliğe sığmayan metni harf harf keser — PDF'e basılan hali döner."""
    while metin and genislik(metin, font, boyut) > en_fazla:
        metin = metin[:-1]
    return metin.rstrip()


def sar(metin, en_fazla, satir_sayisi, font=GOVDE, boyut=8.5):
    """Kelime kelime en çok `satir_sayisi` satıra sarar; artanı son satırdan keser."""
    satirlar, kelimeler = [], metin.split()
    while kelimeler and len(satirlar) < satir_sayisi:
        satir = kelimeler.pop(0)
        while kelimeler and genislik(satir + " " + kelimeler[0], font, boyut) <= en_fazla:
            satir += " " + kelimeler.pop(0)
        satirlar.append(satir)
    if kelimeler:
        satirlar[-1] = kes(satirlar[-1] + " " + " ".join(kelimeler), en_fazla, font, boyut)
    return [kes(s, en_fazla, font, boyut) for s in satirlar]


def yaz(c, x, y, metin, font=GOVDE, boyut=8.5, kelime_kelime=False):
    """kelime_kelime=True: boşluk karakteri basmadan her kelimeyi ayrı konumlar
    (birçok bankanın PDF üreticisi böyle yapar)."""
    c.setFont(font, boyut)
    if not kelime_kelime:
        c.drawString(x, y, metin)
        return
    bosluk = genislik(" ", font, boyut)
    for kelime in metin.split(" "):
        c.drawString(x, y, kelime)
        x += genislik(kelime, font, boyut) + bosluk


def sag_yaz(c, x_sag, y, metin, font=GOVDE, boyut=8.5, kelime_kelime=False):
    yaz(c, x_sag - genislik(metin, font, boyut), y, metin, font, boyut, kelime_kelime)


def csv_yaz(yol, basliklar, satirlar):
    with open(yol, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if basliklar:
            w.writerow(basliklar)
        w.writerows(satirlar)


def csv_oku(yol):
    with open(yol, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))
