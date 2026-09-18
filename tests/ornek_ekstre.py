"""Sahte banka ekstreleri üretir (reportlab) ve beklenen değerleri CSV'ye yazar.

Banka, kişi ve IBAN tamamen uydurmadır.

CSV kolonları: tarih, aciklama, tutar, bakiye, kontrol
- aciklama: PDF'e gerçekten basılan metin (kesilmiş / iki satıra bölünmüşse birleşik hali)
- tutar, bakiye: basılan değerin işaretli karşılığı, '1234.56' biçiminde
- kontrol: '' (not beklenmez) · UYUMSUZ · ILK_DOGRULANAMADI · ILK_KOLONDAN · ILK_ISARET_YOK
"""
import datetime as dt
import os
import random
from decimal import Decimal

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from ortak import GOVDE, KALIN, csv_yaz, fontlari_kaydet, kanonik, sag_yaz, sar, tr, yaz

ACIKLAMALAR = [
    "MARKET ALIŞVERİŞİ ÖRNEK MAHALLESİ ŞUBESİ POS",
    "ELEKTRİK FATURASI ÖDEMESİ ABONE NO 0000123",
    "MAAŞ ÖDEMESİ DENEME TİCARET LTD. ŞTİ. MART DÖNEMİ PERSONEL ÜCRETİ",
    "KİRA ÖDEMESİ",
    "ATM PARA ÇEKME",
    "EFT GELEN HAYALİ YAZILIM A.Ş. FATURA ÖDEMESİ 2026/03 SÖZLEŞME GEREĞİ AYLIK HİZMET BEDELİ",
    "KREDİ KARTI BORÇ ÖDEMESİ",
    "HAVALE GİDEN AİLE BÜTÇESİ",
    "ECZANE ALIŞVERİŞİ",
    "AKARYAKIT İSTASYONU POS HARCAMASI ÇAYYOLU ŞUBESİ",
    "İNTERNET FATURASI",
    "FAİZ TAHAKKUKU",
    "HESAP İŞLETİM ÜCRETİ",
    "SU FATURASI ÖDEMESİ ABONE 00045",
    "ÖĞRENİM ÜCRETİ TAKSİT 2/8 ÖZEL DENEME KOLEJİ İLKÖĞRETİM KADEMESİ",
    "IŞIK DÜKKANI ÇİÇEKÇİLİK",
]

DUZENLER = {
    # İşaret başta, tek tutar kolonu, devreden bakiye var, açıklama iki satıra sarılıyor
    "ekstre_eksi_basta": dict(tohum=11, satir=46, isaret="basta", kolon="tek", devreden=True,
                              sar=True, tutar_hatasi={11}, bakiye_hatasi={29}, baslangic="12345.67"),
    # İşaret sonda, bakiyeden sonra 'TL', açıklama tek satıra kesiliyor, eksi bakiyeye düşüyor
    "ekstre_eksi_sonda": dict(tohum=22, satir=32, isaret="sonda", kolon="tek", sar=False,
                              tl_eki=True, ref_satiri=True, tutar_hatasi={7}, baslangic="1500.00"),
    # Borç ve alacak ayrı kolon, işaret yok; kelimeler boşluk karakteri olmadan konumlanmış;
    # sayfa altlığı yok, 2. sayfanın ilk satırı açıklama hizasında
    "ekstre_borc_alacak": dict(tohum=33, satir=40, isaret=None, kolon="borc_alacak", sar=True,
                               kelime_kelime=True, altlik=False, tutar_hatasi={14}, baslangic="8200.00"),
    # En yeni hareket en üstte
    "ekstre_ters_sirali": dict(tohum=44, satir=22, isaret="basta", kolon="tek", sar=True,
                               ters=True, baslangic="3000.00"),
    # Borç/alacak; ilk satır borç, gerisi alacak → ilk satırın işareti türetilemez
    "ekstre_ilk_isaret_yok": dict(tohum=55, satir=5, isaret=None, kolon="borc_alacak", sar=True,
                                  yalniz_ilk_borc=True, baslangic="500.00"),
}

BOYUT = 8.5
ACIKLAMA_X = 105
SATIR_ARALIGI, DEVAM_ARALIGI = 14, 10
Y_BAS, Y_SON = 704, 100
KOLONLAR = {
    "tek": dict(aciklama_genislik=265, tutar_sag=470, bakiye_sag=555),
    "borc_alacak": dict(aciklama_genislik=205, borc_sag=400, alacak_sag=475, bakiye_sag=555),
}


def _hareketler(ayar):
    rnd = random.Random(ayar["tohum"])
    bakiye = Decimal(ayar["baslangic"])
    tarih = dt.date(2026, 3, 1)
    sonuc = []
    for i in range(ayar["satir"]):
        tarih += dt.timedelta(days=rnd.choice([0, 1, 1, 2]))
        if ayar.get("yalniz_ilk_borc"):
            alacak = i > 0
        else:
            alacak = rnd.random() < 0.3
        if alacak:
            tutar = Decimal(rnd.randint(50000, 900000)) / 100
        else:
            tutar = -Decimal(rnd.randint(500, 350000)) / 100
        bakiye += tutar
        yazili_tutar = tutar
        if i in ayar.get("tutar_hatasi", ()):
            yazili_tutar = tutar + (1 if tutar > 0 else -1)      # basılan tutarda 1 TL hata
        yazili_bakiye = bakiye + (10 if i in ayar.get("bakiye_hatasi", ()) else 0)
        sonuc.append(dict(tarih=tarih, aciklama=rnd.choice(ACIKLAMALAR), gercek_tutar=tutar,
                          tutar=yazili_tutar, bakiye=yazili_bakiye))
    return sonuc


def _beklenen_kontrol(ayar, hareketler):
    """Kronolojik sırada, basılan değerlerle bakiye zincirini bağımsız olarak kurar."""
    isaretli = ayar["kolon"] == "tek"
    onceki = Decimal(ayar["baslangic"]) if ayar.get("devreden") else None
    for h in hareketler:
        if onceki is None:
            h["dogru"] = False
            h["kontrol"] = "ILK"
        elif isaretli:
            h["dogru"] = onceki + h["tutar"] == h["bakiye"]
        else:
            h["dogru"] = abs(h["bakiye"] - onceki) == abs(h["tutar"])
        if "kontrol" not in h:
            h["kontrol"] = "" if h["dogru"] else "UYUMSUZ"
        onceki = h["bakiye"]

    if isaretli:
        for h in hareketler:
            h["beklenen_tutar"] = h["tutar"]
            if h["kontrol"] == "ILK":
                h["kontrol"] = "ILK_DOGRULANAMADI"
        return
    # İşaretsiz düzen: doğrulanan satırlarda hem borç hem alacak varsa kolon konumu öğrenilebilir
    isaretler = {1 if h["tutar"] > 0 else -1 for h in hareketler if h["dogru"]}
    kolon_bilinir = isaretler == {1, -1}
    for h in hareketler:
        if h["dogru"] or kolon_bilinir:
            h["beklenen_tutar"] = h["tutar"]
        else:
            h["beklenen_tutar"] = abs(h["tutar"])
        if h["kontrol"] == "ILK":
            h["kontrol"] = "ILK_KOLONDAN" if kolon_bilinir else "ILK_ISARET_YOK"


def ekstre_uret(ad, klasor):
    fontlari_kaydet()
    ayar = DUZENLER[ad]
    kol = KOLONLAR[ayar["kolon"]]
    kk = ayar.get("kelime_kelime", False)
    hareketler = _hareketler(ayar)
    _beklenen_kontrol(ayar, hareketler)
    basili = list(reversed(hareketler)) if ayar.get("ters") else hareketler

    # Açıklamanın basılacak hali
    for h in basili:
        if ayar["sar"]:
            h["satirlar"] = sar(h["aciklama"], kol["aciklama_genislik"], 2, boyut=BOYUT)
        else:
            h["satirlar"] = sar(h["aciklama"], kol["aciklama_genislik"], 1, boyut=BOYUT)

    # Sayfa planı
    ogeler = []
    if ayar.get("devreden"):
        ogeler.append(("devreden", None, SATIR_ARALIGI))
    for i, h in enumerate(basili):
        # Her 4. hareketin altına tarih kolonu hizasında referans satırı: açıklamaya eklenmemeli
        h["ref"] = "Ref: {:08d}".format(4711 * (i + 1)) if ayar.get("ref_satiri") and i % 4 == 1 else None
        ek = len(h["satirlar"]) - 1 + (1 if h["ref"] else 0)
        ogeler.append(("hareket", h, SATIR_ARALIGI + DEVAM_ARALIGI * ek))
    ogeler.append(("toplam", None, SATIR_ARALIGI))
    sayfalar, y = [[]], Y_BAS
    for tur, h, yukseklik in ogeler:
        if y - yukseklik < Y_SON:
            sayfalar.append([])
            y = Y_BAS
        sayfalar[-1].append((tur, h, y))
        y -= yukseklik

    pdf_yolu = os.path.join(klasor, ad + ".pdf")
    c = canvas.Canvas(pdf_yolu, pagesize=A4)
    c.setTitle("Hesap Ekstresi (sahte test belgesi)")
    eksi = ayar["isaret"] or "basta"
    for sayfa_no, ogeler in enumerate(sayfalar, 1):
        _sayfa_basligi(c, ayar, sayfa_no, len(sayfalar))
        for tur, h, y in ogeler:
            if tur == "devreden":
                yaz(c, 40, y, "01.03.2026", boyut=BOYUT)
                yaz(c, ACIKLAMA_X, y, "DEVREDEN BAKİYE", KALIN, BOYUT)
                sag_yaz(c, kol["bakiye_sag"], y, tr(ayar["baslangic"], eksi), boyut=BOYUT)
            elif tur == "hareket":
                yaz(c, 40, y, h["tarih"].strftime("%d.%m.%Y"), boyut=BOYUT, kelime_kelime=kk)
                for i, parca in enumerate(h["satirlar"]):
                    yaz(c, ACIKLAMA_X, y - i * DEVAM_ARALIGI, parca, boyut=BOYUT, kelime_kelime=kk)
                if h["ref"]:
                    yaz(c, 40, y - len(h["satirlar"]) * DEVAM_ARALIGI, h["ref"], boyut=7.5)
                if ayar["kolon"] == "tek":
                    sag_yaz(c, kol["tutar_sag"], y, tr(h["tutar"], ayar["isaret"]), boyut=BOYUT)
                else:
                    sag = kol["alacak_sag"] if h["tutar"] > 0 else kol["borc_sag"]
                    sag_yaz(c, sag, y, tr(h["tutar"], None), boyut=BOYUT)
                bakiye = tr(h["bakiye"], eksi) + (" TL" if ayar.get("tl_eki") else "")
                sag_yaz(c, kol["bakiye_sag"], y, bakiye, boyut=BOYUT, kelime_kelime=kk)
            else:  # dönem toplamı: hareket değildir
                toplam = sum(x["tutar"] for x in hareketler)
                if ayar.get("tl_eki"):
                    yaz(c, 40, y, "31.03.2026", boyut=BOYUT)
                    yaz(c, ACIKLAMA_X, y, "DÖNEM SONU BAKİYESİ", KALIN, BOYUT)
                else:
                    yaz(c, ACIKLAMA_X, y, "DÖNEM TOPLAMI", KALIN, BOYUT)
                son = hareketler[-1]["bakiye"]
                if ayar["kolon"] == "tek":
                    sag_yaz(c, kol["tutar_sag"], y, tr(toplam, ayar["isaret"]), KALIN, BOYUT)
                else:
                    sag_yaz(c, kol["borc_sag"], y, tr(sum(-x["tutar"] for x in hareketler if x["tutar"] < 0), None), KALIN, BOYUT)
                    sag_yaz(c, kol["alacak_sag"], y, tr(sum(x["tutar"] for x in hareketler if x["tutar"] > 0), None), KALIN, BOYUT)
                sag_yaz(c, kol["bakiye_sag"], y, tr(son, eksi), KALIN, BOYUT)
        if ayar.get("altlik", True):
            _sayfa_altligi(c, sayfa_no, len(sayfalar))
        c.showPage()
    c.save()

    csv_yolu = os.path.join(klasor, ad + ".csv")
    csv_yaz(csv_yolu, ["tarih", "aciklama", "tutar", "bakiye", "kontrol"], [
        [h["tarih"].strftime("%d.%m.%Y"), " ".join(h["satirlar"]), kanonik(h["beklenen_tutar"]),
         kanonik(h["bakiye"]), h["kontrol"]]
        for h in basili])
    return pdf_yolu, csv_yolu


def _sayfa_basligi(c, ayar, sayfa_no, toplam):
    if sayfa_no > 1:
        # Sayfanın ilk satırı açıklama kolonu hizasında: önceki sayfanın son hareketine yapışmamalı
        yaz(c, ACIKLAMA_X, 818, "Önceki sayfadan devam eden hesap hareketleri", boyut=8)
    yaz(c, 40, 800, "HAYALİ BANKA A.Ş.", KALIN, 13)
    sag_yaz(c, 555, 800, "HESAP EKSTRESİ", KALIN, 11)
    yaz(c, 40, 784, "Müşteri: Deneme Kişi", boyut=9)
    sag_yaz(c, 555, 784, "Müşteri No: 000000001", boyut=9)
    yaz(c, 40, 770, "IBAN: TR00 0000 0000 0000 0000 0000 00", boyut=9)
    yaz(c, 40, 756, "Dönem: 01.03.2026 - 30.04.2026", boyut=9)
    yaz(c, 40, 742, "17.09.2026 tarihinde düzenlenmiştir", boyut=9)
    kol = KOLONLAR[ayar["kolon"]]
    yaz(c, 40, 722, "Tarih", KALIN, 9)
    yaz(c, ACIKLAMA_X, 722, "Açıklama", KALIN, 9)   # açıklama kolonuyla aynı hizada başlık
    if ayar["kolon"] == "tek":
        sag_yaz(c, kol["tutar_sag"], 722, "Tutar", KALIN, 9)
    else:
        sag_yaz(c, kol["borc_sag"], 722, "Borç", KALIN, 9)
        sag_yaz(c, kol["alacak_sag"], 722, "Alacak", KALIN, 9)
    sag_yaz(c, kol["bakiye_sag"], 722, "Bakiye", KALIN, 9)
    c.setLineWidth(0.6)
    c.line(40, 716, 555, 716)


def _sayfa_altligi(c, sayfa_no, toplam):
    c.line(40, 70, 555, 70)
    # Açıklama kolonuyla aynı hizada altlık: açıklamaya yapışmamalı
    yaz(c, ACIKLAMA_X, 58, "Bu ekstre bilgi amaçlıdır; sorularınız için şubenize başvurunuz.", boyut=8)
    sag_yaz(c, 555, 40, "Sayfa {} / {}".format(sayfa_no, toplam), boyut=8)
