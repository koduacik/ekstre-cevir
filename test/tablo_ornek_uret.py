#!/usr/bin/env python3
"""Tablo modu için test PDF'leri + beklenen sonuç (JSON).

  cizgili       : kenarlıklı basit tablo (satış raporu)
  cok_sayfa     : 3 sayfaya taşan, başlığı her sayfada tekrarlanan tablo
  cizgisiz      : kenarlıksız, boşlukla hizalı kolonlar
  tarihli_rapor : satırları TARİHLE başlayan ama ekstre OLMAYAN tablo (ekstre sanılmamalı)
  duz_metin     : tablo yok, yalnız paragraf (hata vermeli)
"""
from __future__ import annotations
import json, random
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

pdfmetrics.registerFont(TTFont("A", "/System/Library/Fonts/Supplemental/Arial.ttf"))
BURADA = Path(__file__).parent / "tablo"
stil = getSampleStyleSheet()
for k in ("Title", "Normal"):
    stil[k].fontName = "A"

def tr(x, ondalik=2):
    return f"{x:,.{ondalik}f}".replace(",", "#").replace(".", ",").replace("#", ".")

def cizgili_tablo(veri, tekrar_baslik=False):
    t = Table(veri, repeatRows=1 if tekrar_baslik else 0)
    t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), "A"), ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("ALIGN", (1, 1), (-1, -1), "RIGHT")]))
    return t

beklenen = {}

# 1) çizgili
basliklar = ["Ürün", "Adet", "Birim Fiyat", "Tutar"]
urunler = [("Vida M6", 120, 2.40), ("Somun M6", 120, 1.15), ("Pul 6mm", 240, 0.35),
           ("Dübel 8mm", 60, 1.90), ("Matkap ucu 6mm", 4, 85.00), ("Silikon", 12, 1450.50)]
veri = [basliklar] + [[a, str(n), tr(f), tr(n * f)] for a, n, f in urunler]
SimpleDocTemplate(str(BURADA / "cizgili.pdf"), pagesize=A4).build([Paragraph("Eylül Satış Raporu", stil["Title"]), cizgili_tablo(veri)])
beklenen["cizgili"] = {"basliklar": basliklar, "satirlar": [[a, n, f, round(n * f, 2)] for a, n, f in urunler]}

# 2) çok sayfalı, başlık tekrarı
rnd = random.Random(5)
stok = [(f"STK-{1000+i}", f"Parça {i+1}", rnd.randint(1, 900), round(rnd.uniform(3, 2500), 2)) for i in range(110)]
veri = [["Kod", "Açıklama", "Stok", "Birim Fiyat"]] + [[k, a, str(s), tr(f)] for k, a, s, f in stok]
SimpleDocTemplate(str(BURADA / "cok_sayfa.pdf"), pagesize=A4).build([Paragraph("Stok Listesi", stil["Title"]), cizgili_tablo(veri, tekrar_baslik=True)])
beklenen["cok_sayfa"] = {"basliklar": ["Kod", "Açıklama", "Stok", "Birim Fiyat"], "satirlar": [[k, a, s, f] for k, a, s, f in stok]}

# 3) çizgisiz, boşlukla hizalı
c = canvas.Canvas(str(BURADA / "cizgisiz.pdf"), pagesize=A4)
c.setFont("A", 13); c.drawString(50, 790, "Şube Ciro Özeti")
c.setFont("A", 10)
kolon_x = [50, 220, 330, 440]
for x, b in zip(kolon_x, ["Şube", "İşlem", "Ciro", "Ortalama"]):
    c.drawString(x, 750, b)
subeler = [("Kadıköy", 1840, 412350.75), ("Beşiktaş", 1310, 298110.20), ("Üsküdar", 990, 187400.00),
           ("Bakırköy", 1502, 351020.45), ("Maltepe", 760, 120330.10)]
yy = 730
for ad, n, ciro in subeler:
    c.drawString(50, yy, ad); c.drawRightString(270, yy, tr(n, 0)); c.drawRightString(410, yy, tr(ciro)); c.drawRightString(520, yy, tr(ciro / n))
    yy -= 18
c.save()
beklenen["cizgisiz"] = {"basliklar": ["Şube", "İşlem", "Ciro", "Ortalama"],
                        "satirlar": [[a, n, ciro, round(ciro / n, 2)] for a, n, ciro in subeler]}

# 4) tarihle başlayan ama ekstre olmayan rapor
gunler = [("01.09.2026", 42, 18450.00, 3), ("02.09.2026", 38, 16220.50, 1), ("03.09.2026", 51, 22980.75, 4),
          ("04.09.2026", 47, 20115.00, 2), ("05.09.2026", 60, 27400.25, 5), ("06.09.2026", 29, 11990.00, 0)]
veri = [["Tarih", "Sipariş", "Ciro", "İade"]] + [[g, str(s), tr(c_), str(i)] for g, s, c_, i in gunler]
SimpleDocTemplate(str(BURADA / "tarihli_rapor.pdf"), pagesize=A4).build([Paragraph("Günlük Satış", stil["Title"]), cizgili_tablo(veri)])
beklenen["tarihli_rapor"] = {"basliklar": ["Tarih", "Sipariş", "Ciro", "İade"], "satirlar": [[g, s, c_, i] for g, s, c_, i in gunler]}

# 5) düz metin
SimpleDocTemplate(str(BURADA / "duz_metin.pdf"), pagesize=A4).build(
    [Paragraph("Kira Sözleşmesi", stil["Title"])] +
    [Paragraph("Bu sözleşme 1 Eylül 2026 tarihinde taraflar arasında imzalanmıştır. Kiracı aylık 25.000 TL kira bedelini her ayın 5'ine kadar ödemeyi kabul eder. " * 3, stil["Normal"]) for _ in range(4)])
beklenen["duz_metin"] = None

(BURADA / "beklenen.json").write_text(json.dumps(beklenen, ensure_ascii=False, indent=1), encoding="utf-8")
print("✓", ", ".join(f"{p.name}" for p in sorted(BURADA.glob("*.pdf"))))
