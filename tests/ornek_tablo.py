"""Tablo modu için test belgeleri üretir (reportlab).

Her tablonun beklenen içeriği ayrı CSV'ye yazılır: `<ad>.tablo<N>.csv`.
Hücre biçimi: 's:metin' (metin kalmalı) · 'n:1234.56' (sayı olmalı) · '' (boş).
Firma ve kişi adları uydurmadır.
"""
import datetime as dt
import os
import random
from decimal import Decimal

from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ortak import GOVDE, KALIN, csv_yaz, fontlari_kaydet, sag_yaz, tr, yaz

URUNLER = ["Kurşun Kalem", "Silgi", "Defter A4 Çizgili", "Tükenmez Kalem", "Pergel Takımı",
           "Suluboya 12'li", "Makas", "Cetvel 30 cm", "Dosya Klasörü", "Yapıştırıcı"]


def _s(metin):
    return "s:" + metin


def _n(deger):
    return "n:" + str(deger)


def _stiller():
    fontlari_kaydet()
    govde = ParagraphStyle("govde", fontName=GOVDE, fontSize=10, leading=14, alignment=TA_JUSTIFY)
    baslik = ParagraphStyle("baslik", fontName=KALIN, fontSize=14, leading=18, spaceAfter=8)
    hucre = ParagraphStyle("hucre", fontName=GOVDE, fontSize=9, leading=11)
    return govde, baslik, hucre


def _izgara(kalin_baslik=True):
    return TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), GOVDE),
        ("FONTNAME", (0, 0), (-1, 0), KALIN if kalin_baslik else GOVDE),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, (0, 0, 0)),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ])


def kenarlikli_uret(klasor):
    """Aynı sayfada iki kenarlıklı tablo; birinde iki satıra sarılan hücre var."""
    govde, baslik, hucre = _stiller()
    ad = "tablo_kenarlikli"
    pdf = os.path.join(klasor, ad + ".pdf")

    t1 = [["Ürün Kodu", "Ürün Adı", "Adet", "Birim Fiyat", "Tutar"]]
    b1 = [[_s(x) for x in t1[0]]]
    satirlar = [("00123", "Kurşun Kalem", 12, Decimal("7.50")),
                ("00457", "Çizim Seti Profesyonel Öğrenci Paketi Ahşap Kutulu", 3, Decimal("1250.00")),
                ("01020", "Defter A4 Çizgili", 1250, Decimal("32.40")),
                ("00089", "Silgi", 40, Decimal("4.25"))]
    for kod, ad_, adet, fiyat in satirlar:
        tutar = fiyat * adet
        uzun = len(ad_) > 30
        t1.append([kod, Paragraph(ad_, hucre) if uzun else ad_,
                   "{:,}".format(adet).replace(",", "."), tr(fiyat) + " TL", tr(tutar)])
        b1.append([_s(kod), _s(ad_), _n(adet), _n(fiyat), _n(tutar)])

    t2 = [["Şube", "Telefon", "Açılış Tarihi", "Ciro (TL)", "Değişim"]]
    b2 = [[_s(x) for x in t2[0]]]
    for sube, tel, tarih, ciro, degisim, gosterim in [
            ("Merkez", "05001112233", "01.02.2019", Decimal("1234567.89"), Decimal("-2.50"), "-2,50"),
            ("Çarşı", "05002223344", "15.06.2021", Decimal("98765.40"), Decimal("-3.75"), "3,75-"),
            ("İstasyon", "02120000000", "03.11.2023", Decimal("45000.00"), Decimal("12.00"), "12,00")]:
        t2.append([sube, tel, tarih, tr(ciro), gosterim])
        b2.append([_s(sube), _s(tel), _s(tarih), _n(ciro), _n(degisim)])

    hikaye = [
        Paragraph("Hayali Kırtasiye — Mart 2026 Sipariş Özeti", baslik),
        Paragraph("Aşağıdaki tablo 31.03.2026 tarihine kadar alınan siparişleri gösterir. "
                  "Fiyatlara KDV dahildir; 1.000,00 TL üzeri siparişlerde kargo ücretsizdir.", govde),
        Spacer(1, 10),
        Table(t1, colWidths=[70, 190, 50, 90, 90], style=_izgara()),
        Spacer(1, 20),
        Paragraph("Şubelerin iletişim bilgileri ve ciro değişimleri:", govde),
        Spacer(1, 8),
        Table(t2, colWidths=[80, 100, 90, 110, 70], style=_izgara()),
    ]
    SimpleDocTemplate(pdf, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=50,
                      bottomMargin=50).build(hikaye)
    return pdf, [_yaz_csv(klasor, ad, 1, b1), _yaz_csv(klasor, ad, 2, b2)]


def bolunmus_uret(klasor):
    """Üç sayfaya bölünen, başlığı her sayfada tekrarlanan kenarlıklı tablo."""
    govde, baslik, _ = _stiller()
    ad = "tablo_bolunmus"
    pdf = os.path.join(klasor, ad + ".pdf")
    rnd = random.Random(7)
    veri = [["Sıra", "Tarih", "Müşteri Kodu", "Açıklama", "Tutar"]]
    beklenen = [[_s(x) for x in veri[0]]]
    tarih = dt.date(2026, 1, 2)
    for sira in range(1, 121):
        tarih += dt.timedelta(days=rnd.choice([0, 1]))
        kod = "0" + str(rnd.randint(100000, 999999))
        aciklama = rnd.choice(["Tahsilat", "İade", "Peşin satış", "Çek tahsilatı", "Havale ile ödeme"])
        tutar = Decimal(rnd.randint(1000, 9999999)) / 100
        veri.append([str(sira), tarih.strftime("%d.%m.%Y"), kod, aciklama, tr(tutar) + " TL"])
        beklenen.append([_n(sira), _s(tarih.strftime("%d.%m.%Y")), _s(kod), _s(aciklama), _n(tutar)])
    stil = _izgara()
    stil.add("ALIGN", (2, 1), (3, -1), "LEFT")
    hikaye = [Paragraph("Tahsilat Listesi — Ocak-Nisan 2026", baslik),
              Table(veri, colWidths=[40, 80, 100, 170, 110], style=stil, repeatRows=1)]
    SimpleDocTemplate(pdf, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=50,
                      bottomMargin=50).build(hikaye)
    return pdf, [_yaz_csv(klasor, ad, 1, beklenen)]


def kenarsiz_uret(klasor):
    """Çizgisiz, iki sayfaya bölünmüş stok tablosu; sayılar sağa, metinler sola hizalı."""
    fontlari_kaydet()
    ad = "tablo_kenarsiz"
    pdf = os.path.join(klasor, ad + ".pdf")
    rnd = random.Random(8)
    kolonlar = [("Depo", "L", 40), ("Ürün", "L", 110), ("Kod", "L", 250), ("Miktar", "R", 340),
                ("Birim Fiyat", "R", 420), ("Tutar", "R", 490), ("Değişim", "R", 555)]
    beklenen = [[_s(k[0]) for k in kolonlar]]
    satirlar = []
    for _ in range(55):
        miktar = rnd.randint(1, 25000)
        fiyat = Decimal(rnd.randint(100, 99999)) / 100
        tutar = fiyat * miktar
        secim = rnd.random()
        degisim = None if secim < 0.25 else Decimal(rnd.randint(-50000, 50000)) / 100
        depo, urun, kod = rnd.choice(["Ankara", "İzmir", "Gaziantep"]), rnd.choice(URUNLER), "00" + str(rnd.randint(100, 999))
        satirlar.append([depo, urun, kod, "{:,}".format(miktar).replace(",", "."), tr(fiyat) + " TL",
                         tr(tutar), "" if degisim is None else tr(degisim)])
        beklenen.append([_s(depo), _s(urun), _s(kod), _n(miktar), _n(fiyat), _n(tutar),
                         "" if degisim is None else _n(degisim)])

    c = canvas.Canvas(pdf, pagesize=A4)
    parcalar = [satirlar[:30], satirlar[30:]]
    for sayfa_no, parca in enumerate(parcalar, 1):
        if sayfa_no == 1:
            yaz(c, 40, 800, "HAYALİ LOJİSTİK A.Ş. — Depo Stok Raporu", KALIN, 12)
            yaz(c, 40, 780, "Bu rapor 31.03.2026 tarihi itibarıyla hazırlanmıştır. Toplam 3 depoda 1.250 çeşit ürün", boyut=9)
            yaz(c, 40, 767, "bulunmaktadır; stok değeri bir önceki aya göre %4,5 artarak 2.345.678,90 TL olmuştur.", boyut=9)
            y = 735
        else:
            yaz(c, 40, 800, "Depo Stok Raporu (devam)", KALIN, 12)
            y = 770
        for baslik, hiza, x in kolonlar:
            (yaz if hiza == "L" else sag_yaz)(c, x, y, baslik, KALIN, 9)
        y -= 18
        for satir in parca:
            for metin, (_, hiza, x) in zip(satir, kolonlar):
                if metin:
                    (yaz if hiza == "L" else sag_yaz)(c, x, y, metin, GOVDE, 9)
            y -= 14
        if sayfa_no == 2:
            y -= 20
            yaz(c, 40, y, "Açıklama: Değişim kolonu, 28.02.2026 sayımına göre farkı gösterir. Sayımda 12 kalem", boyut=9)
            yaz(c, 40, y - 13, "ürün için 1.500,00 TL eksik bulunmuş, 3 kalem ürün için 250,75 TL fazla bulunmuştur.", boyut=9)
        yaz(c, 40, 40, "Hayali Lojistik — iç kullanım içindir", boyut=8)
        sag_yaz(c, 555, 40, "Sayfa {} / 2".format(sayfa_no), boyut=8)
        c.showPage()
    c.save()
    return pdf, [_yaz_csv(klasor, ad, 1, beklenen)]


def satis_raporu_uret(klasor):
    """Satırları tarihle başlayan, ama bakiye içermeyen günlük satış raporu."""
    fontlari_kaydet()
    ad = "tablo_satis_raporu"
    pdf = os.path.join(klasor, ad + ".pdf")
    rnd = random.Random(9)
    kolonlar = [("Tarih", "L", 40), ("Şube", "L", 110), ("Ürün", "L", 190), ("Adet", "R", 360),
                ("Birim Fiyat", "R", 450), ("Tutar", "R", 555)]
    beklenen = [[_s(k[0]) for k in kolonlar]]
    c = canvas.Canvas(pdf, pagesize=A4)
    yaz(c, 40, 800, "Günlük Satış Raporu — Hayali Kırtasiye", KALIN, 13)
    yaz(c, 40, 784, "Rapor tarihi: 17.09.2026", boyut=9)
    y = 755
    for baslik, hiza, x in kolonlar:
        (yaz if hiza == "L" else sag_yaz)(c, x, y, baslik, KALIN, 9)
    y -= 18
    tarih, toplam_adet, toplam_tutar = dt.date(2026, 3, 1), 0, Decimal(0)
    for _ in range(25):
        tarih += dt.timedelta(days=rnd.choice([0, 1]))
        sube, urun = rnd.choice(["Merkez", "Çarşı", "İstasyon"]), rnd.choice(URUNLER)
        adet, fiyat = rnd.randint(1, 60), Decimal(rnd.randint(250, 45000)) / 100
        tutar = fiyat * adet
        toplam_adet += adet
        toplam_tutar += tutar
        metinler = [tarih.strftime("%d.%m.%Y"), sube, urun, str(adet), tr(fiyat), tr(tutar)]
        for metin, (_, hiza, x) in zip(metinler, kolonlar):
            (yaz if hiza == "L" else sag_yaz)(c, x, y, metin, GOVDE, 9)
        beklenen.append([_s(metinler[0]), _s(sube), _s(urun), _n(adet), _n(fiyat), _n(tutar)])
        y -= 14
    c.line(40, y + 9, 555, y + 9)
    y -= 4
    yaz(c, 40, y, "Toplam", KALIN, 9)
    sag_yaz(c, 360, y, str(toplam_adet), KALIN, 9)
    sag_yaz(c, 555, y, tr(toplam_tutar), KALIN, 9)
    beklenen.append([_s("Toplam"), "", "", _n(toplam_adet), "", _n(toplam_tutar)])
    c.showPage()
    c.save()
    return pdf, [_yaz_csv(klasor, ad, 1, beklenen)]


def paragraf_uret(klasor):
    """Yalnızca paragraflardan oluşan belge: içinde sayı, tarih ve tutar geçiyor."""
    govde, baslik, _ = _stiller()
    ad = "paragraf"
    pdf = os.path.join(klasor, ad + ".pdf")
    metin = ("Hayali Danışmanlık A.Ş. 2026 yılının ilk çeyreğinde 1.250.000,00 TL ciroya ulaşmıştır. "
             "01.01.2026 ile 31.03.2026 arasında 45 yeni müşteriyle 128 sözleşme imzalanmış, ortalama "
             "sözleşme bedeli 9.765,63 TL olmuştur. Bu tutar geçen yılın aynı dönemine göre %12,5 "
             "artışı ifade eder. Giderler 830.400,50 TL, vergi öncesi kâr 419.599,50 TL olarak "
             "gerçekleşmiştir. Önümüzdeki dönemde 3 yeni şube açılması, 25 kişilik ekibin 40 kişiye "
             "çıkarılması ve 2.000.000,00 TL ciro hedefine ulaşılması planlanmaktadır. ")
    hikaye = [Paragraph("Yönetim Kurulu Faaliyet Özeti", baslik)]
    for i in range(14):
        hikaye.append(Paragraph("{}. bölüm — ".format(i + 1) + metin * 2, govde))
        hikaye.append(Spacer(1, 8))
    SimpleDocTemplate(pdf, pagesize=A4, leftMargin=60, rightMargin=60, topMargin=60,
                      bottomMargin=60).build(hikaye)
    return pdf, []


def bos_uret(klasor):
    """Hiç metni olmayan (taranmış belge gibi) PDF."""
    pdf = os.path.join(klasor, "metinsiz.pdf")
    c = canvas.Canvas(pdf, pagesize=A4)
    c.rect(100, 400, 300, 200, fill=1)
    c.showPage()
    c.save()
    return pdf, []


def _yaz_csv(klasor, ad, no, satirlar):
    yol = os.path.join(klasor, "{}.tablo{}.csv".format(ad, no))
    csv_yaz(yol, None, satirlar)
    return yol


URETICILER = {
    "tablo_kenarlikli": kenarlikli_uret,
    "tablo_bolunmus": bolunmus_uret,
    "tablo_kenarsiz": kenarsiz_uret,
    "tablo_satis_raporu": satis_raporu_uret,
    "paragraf": paragraf_uret,
    "metinsiz": bos_uret,
}
