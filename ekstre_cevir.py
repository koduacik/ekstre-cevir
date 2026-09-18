#!/usr/bin/env python3
"""Ekstre Çevir — PDF banka ekstresini (ya da PDF'teki tabloları) Excel'e çevirir.

Kullanım:
    python ekstre_cevir.py belge.pdf          # çevirir, sonucu anlatır
    python ekstre_cevir.py --yol belge.pdf    # çevirir, yalnızca Excel dosyasının yolunu yazar

Çıkış kodu: 0 başarılı, 1 hata. Hata mesajları stderr'e Türkçe yazılır.
Program hiçbir ağ çağrısı yapmaz; dosyalar bilgisayardan çıkmaz.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Ayarlar
# ---------------------------------------------------------------------------

# Kelime birleştirme toleransı yazı boyutuna oranla: 0,15 em. Boşluk karakteri
# yazmayıp kelimeleri konumla ayıran PDF'lerde sabit 3 pt, küçük puntoda
# kelimeleri birbirine yapıştırıyor.
X_TOLERANS_ORANI = 0.15

HIZA_TOLERANSI = 3.0          # pt — açıklama kolonu hizası
KENAR_TOLERANSI = 2.5         # pt — sağa hizalı sayıların ortak sağ kenarı
KURUS_TOLERANSI = Decimal("0.005")
EKSTRE_DEGIL_ORANI = 0.70     # doğrulanamayan satır oranı bu kadar ya da fazlaysa ekstre değil

BASLIKLAR_EKSTRE = ["Tarih", "Açıklama", "Tutar", "Bakiye", "Kontrol"]


class KullaniciHatasi(Exception):
    """Kullanıcıya olduğu gibi gösterilecek Türkçe hata."""


# ---------------------------------------------------------------------------
# Metin ve sayı yardımcıları
# ---------------------------------------------------------------------------

TARIH_RE = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")
PARA_BIRIMI = {"TL", "TRY", "₺"}
EKSILER = "-−–"  # tire, eksi işareti, kısa çizgi

# Ekstre modu: kuruşlu Türk sayısı, işaret başta ya da sonda.
EKSTRE_SAYI_RE = re.compile(
    r"^([" + re.escape("+" + EKSILER) + r"])?((?:\d{1,3}(?:\.\d{3})+|\d+),\d{2})"
    r"([" + re.escape("+" + EKSILER) + r"])?$"
)


def tarih_coz(metin: str) -> Optional[dt.date]:
    m = TARIH_RE.match(metin)
    if not m:
        return None
    try:
        return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def ekstre_sayisi(metin: str) -> Optional[Tuple[Decimal, Optional[str]]]:
    """'1.234,56-' → (Decimal('1234.56'), '-'). İşaret yoksa ikinci değer None."""
    m = EKSTRE_SAYI_RE.match(metin)
    if not m or (m.group(1) and m.group(3)):
        return None
    deger = Decimal(m.group(2).replace(".", "").replace(",", "."))
    isaret = m.group(1) or m.group(3)
    if isaret:
        isaret = "+" if isaret == "+" else "-"
    return deger, isaret


def tr_sayi(d: Decimal) -> str:
    """Decimal('-1234.5') → '-1.234,50'"""
    metin = f"{abs(d):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if d < 0 else "") + metin


_KATLAMA = str.maketrans("çğıöşüâîûÇĞIİÖŞÜÂÎÛ", "cgiosuaiuCGIIOSUAIU")


def sade(metin: str) -> str:
    """Türkçe küçük harf + aksan katlama: 'DEVREDEN BAKİYE' → 'devreden bakiye'."""
    metin = unicodedata.normalize("NFC", metin).translate(_KATLAMA).lower()
    metin = unicodedata.normalize("NFD", metin)
    metin = "".join(c for c in metin if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", metin).strip()


# ---------------------------------------------------------------------------
# Kelimeler ve satırlar
# ---------------------------------------------------------------------------

@dataclass
class Kelime:
    metin: str
    x0: float
    x1: float
    top: float
    bottom: float

    @property
    def yukseklik(self) -> float:
        return max(self.bottom - self.top, 1.0)


@dataclass
class Satir:
    sayfa: int
    kelimeler: List[Kelime]

    @property
    def top(self) -> float:
        return min(k.top for k in self.kelimeler)

    @property
    def bottom(self) -> float:
        return max(k.bottom for k in self.kelimeler)

    @property
    def x0(self) -> float:
        return self.kelimeler[0].x0

    @property
    def x1(self) -> float:
        return max(k.x1 for k in self.kelimeler)

    @property
    def yukseklik(self) -> float:
        return sorted(k.yukseklik for k in self.kelimeler)[len(self.kelimeler) // 2]

    @property
    def metin(self) -> str:
        return " ".join(k.metin for k in self.kelimeler)


def sayfa_kelimeleri(sayfa, disarida_kutular=()) -> List[Kelime]:
    ham = sayfa.extract_words(
        x_tolerance_ratio=X_TOLERANS_ORANI, y_tolerance=3, keep_blank_chars=False
    )
    kelimeler = []
    for w in ham:
        if not w.get("upright", True):
            continue  # döndürülmüş yazı (filigran vb.)
        metin = unicodedata.normalize("NFC", w["text"]).strip()
        if not metin:
            continue
        k = Kelime(metin, float(w["x0"]), float(w["x1"]), float(w["top"]), float(w["bottom"]))
        orta_x, orta_y = (k.x0 + k.x1) / 2, (k.top + k.bottom) / 2
        if any(x0 <= orta_x <= x1 and t <= orta_y <= b for x0, t, x1, b in disarida_kutular):
            continue
        kelimeler.append(k)
    return kelimeler


def satirlara_ayir(kelimeler: List[Kelime], sayfa_no: int) -> List[Satir]:
    """Kelimeleri dikey merkezlerine göre satırlara toplar (tablo çizgilerine bakmaz)."""
    satirlar: List[Satir] = []
    merkezler: List[float] = []
    for k in sorted(kelimeler, key=lambda k: ((k.top + k.bottom) / 2, k.x0)):
        merkez = (k.top + k.bottom) / 2
        if satirlar:
            son = satirlar[-1]
            if abs(merkez - merkezler[-1]) <= max(1.5, 0.45 * min(k.yukseklik, son.yukseklik)):
                son.kelimeler.append(k)
                n = len(son.kelimeler)
                merkezler[-1] += (merkez - merkezler[-1]) / n
                continue
        satirlar.append(Satir(sayfa_no, [k]))
        merkezler.append(merkez)
    for s in satirlar:
        s.kelimeler.sort(key=lambda k: k.x0)
    return satirlar


# ---------------------------------------------------------------------------
# 1) Banka ekstresi
# ---------------------------------------------------------------------------

ACILIS_RE = re.compile(
    r"^(devreden|devir bakiye|nakli yekun|onceki (donem )?bakiye|acilis bakiye|donem basi bakiye)"
)
HAREKET_DEGIL_RE = re.compile(
    ACILIS_RE.pattern + r"|^(kapanis|donem sonu|(donem |genel |ara |sayfa )?toplam)"
)

MSJ_ILK_DOGRULANAMADI = "İlk hareket: önceki bakiye yok, tutar doğrulanamadı"
MSJ_ILK_ISARET_YOK = "İlk hareket: önceki bakiye yok, işaret türetilemedi"
MSJ_KOLONDAN = "işaret kolon konumundan alındı"


@dataclass
class Hareket:
    sayfa: int
    tarih: dt.date
    aciklama: List[str]
    tutar_mutlak: Decimal
    tutar_isaret: Optional[str]      # '+', '-' ya da None (ekstrede işaret yok)
    bakiye: Decimal
    tutar_x0: float
    tutar_x1: float
    aciklama_x0: List[float]         # devam satırının hizalanabileceği sol kenarlar
    son_bottom: float
    tutar: Decimal = Decimal(0)      # işaretli, sonuç
    kontrol: str = ""
    dogrulandi: bool = False


def _sayi_ve_isaret(kel: List[Kelime], i: int, alt_sinir: int) -> Tuple[Decimal, Optional[str], int]:
    """kel[i] sayısını çözer; hemen solunda ayrı duran '-' işaretini de yakalar."""
    deger, isaret = ekstre_sayisi(kel[i].metin)
    bas = i
    if isaret is None and i - 1 > alt_sinir:
        onceki = kel[i - 1]
        if onceki.metin in ("+",) or (len(onceki.metin) == 1 and onceki.metin in EKSILER):
            if kel[i].x0 - onceki.x1 < 0.6 * kel[i].yukseklik:
                isaret = "+" if onceki.metin == "+" else "-"
                bas = i - 1
    return deger, isaret, bas


def hareket_satiri(satir: Satir) -> Optional[Hareket]:
    kel = satir.kelimeler
    tarih = tarih_coz(kel[0].metin)
    if tarih is None:
        return None
    sayi_yerleri = [i for i in range(1, len(kel)) if ekstre_sayisi(kel[i].metin)]
    if len(sayi_yerleri) < 2:
        return None
    i_tutar, i_bakiye = sayi_yerleri[-2], sayi_yerleri[-1]
    tutar, isaret, bas = _sayi_ve_isaret(kel, i_tutar, 0)
    bakiye, b_isaret, _ = _sayi_ve_isaret(kel, i_bakiye, i_tutar)
    if b_isaret == "-":
        bakiye = -bakiye

    aciklama = kel[1:bas]
    while aciklama and aciklama[-1].metin.upper() in PARA_BIRIMI:
        aciklama = aciklama[:-1]
    hizalar = []
    if aciklama:
        hizalar.append(aciklama[0].x0)
        tarihsiz = [k for k in aciklama if not tarih_coz(k.metin)]
        if tarihsiz:
            hizalar.append(tarihsiz[0].x0)  # işlem + valör tarihi olan düzenler
    return Hareket(
        sayfa=satir.sayfa, tarih=tarih, aciklama=[k.metin for k in aciklama],
        tutar_mutlak=tutar, tutar_isaret=isaret, bakiye=bakiye,
        tutar_x0=kel[bas].x0, tutar_x1=kel[i_tutar].x1,
        aciklama_x0=hizalar, son_bottom=satir.bottom,
    )


def devam_satiri_mi(satir: Satir, h: Hareket) -> bool:
    """Tarihsiz satır, bir önceki hareketin açıklamasının devamı mı?"""
    if satir.sayfa != h.sayfa or not h.aciklama_x0:
        return False
    if tarih_coz(satir.kelimeler[0].metin):
        return False
    if not any(abs(satir.x0 - x) <= HIZA_TOLERANSI for x in h.aciklama_x0):
        return False
    if satir.x1 > h.tutar_x0 - 1:          # tutar kolonuna taşan satır açıklama değil
        return False
    bosluk = satir.top - h.son_bottom
    if not -0.5 * satir.yukseklik <= bosluk <= 2.0 * satir.yukseklik:   # üstte ya da uzakta: altlık vb.
        return False
    return True


def _son_sayi(kelimeler: List[Kelime]) -> Optional[Decimal]:
    for i in range(len(kelimeler) - 1, -1, -1):
        if ekstre_sayisi(kelimeler[i].metin):
            deger, isaret, _ = _sayi_ve_isaret(kelimeler, i, -1)
            return -deger if isaret == "-" else deger
    return None


def _degerlendir(h: Hareket, onceki: Optional[Decimal], isaretli: bool,
                 varsayilan: int, kolon_isareti) -> Tuple[Decimal, str, bool]:
    B, M = h.bakiye, h.tutar_mutlak
    if isaretli:
        if h.tutar_isaret is None:
            A = M * varsayilan
        else:
            A = M if h.tutar_isaret == "+" else -M
        if onceki is None:
            return A, MSJ_ILK_DOGRULANAMADI, False
        beklenen = onceki + A
        if abs(beklenen - B) <= KURUS_TOLERANSI:
            return A, "", True
        return A, (f"Bakiye tutmuyor: önceki bakiye {tr_sayi(onceki)} + tutar {tr_sayi(A)}"
                   f" = {tr_sayi(beklenen)}, ekstrede {tr_sayi(B)}"), False

    # İşaretsiz düzen (borç/alacak ayrı kolon): işaret bakiye farkından
    isaret = kolon_isareti(h) if kolon_isareti else None
    if onceki is not None:
        fark = B - onceki
        if abs(abs(fark) - M) <= KURUS_TOLERANSI:
            return (M if fark >= 0 else -M), "", True
        ek = MSJ_KOLONDAN if isaret else "işaret türetilemedi"
        return M * (isaret or 1), (f"Bakiye tutmuyor: bakiye farkı {tr_sayi(fark)}, "
                                   f"tutar {tr_sayi(M)}; {ek}"), False
    if isaret:
        return M * isaret, f"{MSJ_ILK_DOGRULANAMADI}; {MSJ_KOLONDAN}", False
    return M, MSJ_ILK_ISARET_YOK, False


def _zincir(hareketler, sira, acilis, isaretli, varsayilan, kolon_isareti):
    sonuclar = {}
    onceki = acilis
    for i in sira:
        sonuclar[i] = _degerlendir(hareketler[i], onceki, isaretli, varsayilan, kolon_isareti)
        onceki = hareketler[i].bakiye
    return sonuclar


def _kolon_haritasi(hareketler: List[Hareket], sonuclar) -> Optional[object]:
    """Doğrulanmış satırlardan 'hangi x konumundaki tutar borç, hangisi alacak' öğrenir."""
    kumeler: List[List] = []   # [merkez_x1, {işaretler}]
    for i, (tutar, _, dogru) in sonuclar.items():
        if not dogru or tutar == 0:
            continue
        x1, isaret = hareketler[i].tutar_x1, (1 if tutar > 0 else -1)
        for kume in kumeler:
            if abs(kume[0] - x1) <= KENAR_TOLERANSI:
                kume[1].add(isaret)
                break
        else:
            kumeler.append([x1, {isaret}])
    saf = [(x, next(iter(s))) for x, s in kumeler if len(s) == 1]
    if not ({i for _, i in saf} >= {1, -1}):
        return None

    def kolon_isareti(h: Hareket) -> Optional[int]:
        yakin = [(abs(x - h.tutar_x1), i) for x, i in saf if abs(x - h.tutar_x1) <= KENAR_TOLERANSI * 2]
        return min(yakin)[1] if yakin else None

    return kolon_isareti


@dataclass
class EkstreSonucu:
    hareketler: List[Hareket]
    dogrulanan: int

    @property
    def ekstre_mi(self) -> bool:
        if not self.hareketler:
            return False
        dogrulanamayan = len(self.hareketler) - self.dogrulanan
        return dogrulanamayan / len(self.hareketler) < EKSTRE_DEGIL_ORANI


def ekstre_coz(sayfalar: List[List[Satir]]) -> EkstreSonucu:
    hareketler: List[Hareket] = []
    acilis_once: Optional[Decimal] = None
    acilis_sonra: Optional[Decimal] = None

    for satirlar in sayfalar:
        acik: Optional[Hareket] = None           # açıklaması devam edebilecek hareket
        for s in satirlar:
            kel = s.kelimeler
            govde = kel[1:] if tarih_coz(kel[0].metin) else kel
            sd = sade(" ".join(k.metin for k in govde))
            if ACILIS_RE.match(sd):
                deger = _son_sayi(govde)
                if deger is not None:
                    if not hareketler and acilis_once is None:
                        acilis_once = deger
                    elif hareketler:
                        acilis_sonra = deger
                acik = None
                continue
            if HAREKET_DEGIL_RE.match(sd):
                acik = None
                continue
            h = hareket_satiri(s)
            if h is not None:
                hareketler.append(h)
                acilis_sonra = None
                acik = h
                continue
            if acik is not None and devam_satiri_mi(s, acik):
                acik.aciklama.extend(k.metin for k in kel)
                acik.son_bottom = s.bottom
                continue
            acik = None

    if not hareketler:
        return EkstreSonucu([], 0)

    isaretli = any(h.tutar_isaret for h in hareketler)
    varsayilan = 1 if any(h.tutar_isaret == "-" for h in hareketler) else -1
    ileri = list(range(len(hareketler)))
    adaylar = [
        (ileri, acilis_once),
        (ileri[::-1], acilis_sonra),   # en yeni hareket üstte olan ekstreler
    ]
    en_iyi = None
    for sira, acilis in adaylar:
        sonuclar = _zincir(hareketler, sira, acilis, isaretli, varsayilan, None)
        sayi = sum(1 for _, _, d in sonuclar.values() if d)
        if en_iyi is None or sayi > en_iyi[0]:
            en_iyi = (sayi, sira, acilis, sonuclar)
    _, sira, acilis, sonuclar = en_iyi

    if not isaretli:
        kolon_isareti = _kolon_haritasi(hareketler, sonuclar)
        if kolon_isareti:
            sonuclar = _zincir(hareketler, sira, acilis, isaretli, varsayilan, kolon_isareti)

    dogrulanan = 0
    for i, (tutar, kontrol, dogru) in sonuclar.items():
        h = hareketler[i]
        h.tutar, h.kontrol, h.dogrulandi = tutar, kontrol, dogru
        dogrulanan += dogru
    return EkstreSonucu(hareketler, dogrulanan)


# ---------------------------------------------------------------------------
# 3) Tablo modu
# ---------------------------------------------------------------------------

def _para_birimini_at(metin: str) -> str:
    return re.sub(r"^₺\s*|\s*(?:TL|TRY|₺)$", "", metin.strip())


def hucre_degeri(metin: str):
    """Hücre metnini Excel değerine çevirir → (değer, sayı biçimi).

    '1.234,56' ve '1.250,00 TL' sayı olur; '0532…' gibi baştaki sıfırlı kodlar
    ve '01.03.2026' gibi tarihler metin kalır.
    """
    s = re.sub(r"\s+", " ", metin or "").strip()
    if not s:
        return None, None
    t = _para_birimini_at(s)
    isaret = 1
    if t[:1] and t[0] in EKSILER + "+":
        isaret = 1 if t[0] == "+" else -1
        t = t[1:].lstrip()
    elif t[-1:] and t[-1] in EKSILER:
        isaret, t = -1, t[:-1].rstrip()
    m = re.fullmatch(r"(\d{1,3}(?:\.\d{3})+|\d+),(\d+)", t)
    if m:
        tam = m.group(1)
        if len(tam) > 1 and tam[0] == "0":
            return s, None
        deger = Decimal(tam.replace(".", "") + "." + m.group(2)) * isaret
        return float(deger), "#,##0." + "0" * len(m.group(2))
    if re.fullmatch(r"[1-9]\d{0,2}(?:\.\d{3})+", t):
        return int(t.replace(".", "")) * isaret, "#,##0"
    if re.fullmatch(r"0|[1-9]\d{0,14}", t):
        return int(t) * isaret, None
    return s, None


def _sayi_hucresi_mi(metin: str) -> bool:
    return isinstance(hucre_degeri(metin)[0], (int, float))


def _hizali_sayi_mi(metin: str) -> bool:
    """Kolon kenarı bulmak için sayı sayılan hücre (değerler, rakam kodları, yüzdeler)."""
    t = _para_birimini_at(metin).strip("+" + EKSILER).strip()
    return bool(re.fullmatch(r"(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?|%\d+(?:,\d+)?|\d+(?:,\d+)?%", t))


def basliga_benzer(satir: List[str]) -> bool:
    return any(satir) and not any(_sayi_hucresi_mi(h) for h in satir)


@dataclass
class Tablo:
    satirlar: List[List[str]]
    capalar: List[Tuple[str, float]]   # kolon imzası, sayfalar arası birleştirme için
    sayfa_ilk: int
    sayfa_son: int
    top: float


def cizgili_tablolar(sayfa, sayfa_no: int) -> List[Tuple[Tablo, Tuple[float, float, float, float]]]:
    sonuc = []
    for t in sayfa.find_tables():
        satirlar = [[re.sub(r"\s+", " ", h or "").strip() for h in r] for r in t.extract()]
        satirlar = [r for r in satirlar if any(r)]
        if len(satirlar) < 2 or max(len(r) for r in satirlar) < 2:
            continue
        kenarlar = sorted({round(c[0], 1) for c in t.cells} | {round(c[2], 1) for c in t.cells})
        tablo = Tablo(satirlar, [("K", x) for x in kenarlar], sayfa_no, sayfa_no, t.bbox[1])
        sonuc.append((tablo, t.bbox))
    return sonuc


@dataclass
class Hucre:
    metin: str
    x0: float
    x1: float


def hucrelere_bol(satir: Satir) -> List[Hucre]:
    """Aralarında sözcük boşluğundan geniş açıklık olan kelime gruplarını hücre sayar."""
    hucreler: List[Hucre] = []
    for k in satir.kelimeler:
        if hucreler and k.x0 - hucreler[-1].x1 <= 0.6 * k.yukseklik:
            son = hucreler[-1]
            son.metin += " " + k.metin
            son.x1 = k.x1
        else:
            hucreler.append(Hucre(k.metin, k.x0, k.x1))
    return hucreler


def _kumele(degerler: List[Tuple[float, int]], tolerans: float) -> List[Tuple[float, set]]:
    """(x, satır_no) çiftlerini x'e göre kümeler → [(ortalama_x, {satır_no})]."""
    kumeler: List[List] = []
    for x, no in sorted(degerler):
        if kumeler and x - kumeler[-1][0][-1] <= tolerans:
            kumeler[-1][0].append(x)
            kumeler[-1][1].add(no)
        else:
            kumeler.append([[x], {no}])
    return [(sum(xs) / len(xs), nolar) for xs, nolar in kumeler]


def _sayi_kenarlari(hucreli, nolar, en_az: int) -> List[float]:
    xs = [(h.x1, no) for no in nolar for h in hucreli[no][1] if _hizali_sayi_mi(h.metin)]
    return [x for x, destek in _kumele(xs, KENAR_TOLERANSI) if len(destek) >= en_az]


def cizgisiz_tablolar(satirlar: List[Satir], sayfa_no: int) -> List[Tablo]:
    hucreli = [(s, hucrelere_bol(s)) for s in satirlar]
    tum = range(len(hucreli))
    kenarlar = _sayi_kenarlari(hucreli, tum, 2)

    def capali(no: int, kenar_listesi: List[float]) -> bool:
        hs = hucreli[no][1]
        return len(hs) >= 2 and any(
            _hizali_sayi_mi(h.metin) and abs(h.x1 - e) <= KENAR_TOLERANSI
            for h in hs for e in kenar_listesi)

    # Kenara oturan ardışık satırlardan bloklar
    bloklar: List[List[int]] = []
    for no in tum:
        if not capali(no, kenarlar):
            continue
        s = hucreli[no][0]
        if bloklar and bloklar[-1][-1] == no - 1:
            onceki = hucreli[no - 1][0]
            if s.top - onceki.bottom <= 2.5 * s.yukseklik:
                bloklar[-1].append(no)
                continue
        bloklar.append([no])

    tablolar = []
    for blok in bloklar:
        n = len(blok)
        if n < 2:
            continue
        blok_kenarlari = _sayi_kenarlari(hucreli, blok, max(2, -(-3 * n // 10)))
        destekler = [len({no for no in blok for h in hucreli[no][1]
                          if _hizali_sayi_mi(h.metin) and abs(h.x1 - e) <= KENAR_TOLERANSI})
                     for e in blok_kenarlari]
        if n >= 3 and not any(d >= 3 for d in destekler):
            continue
        if n == 2 and sum(1 for d in destekler if d >= 2) < 2:
            continue
        tablo = _blogu_tabloya_cevir(hucreli, blok, blok_kenarlari, sayfa_no)
        if tablo:
            tablolar.append(tablo)
    return tablolar


def _blogu_tabloya_cevir(hucreli, blok: List[int], kenarlar: List[float], sayfa_no: int) -> Optional[Tablo]:
    # Başlık: bloğun hemen üstündeki, sayı içermeyen, en az iki hücreli satır
    baslik_no = None
    ilk = blok[0]
    if ilk > 0:
        s_ust, hs_ust = hucreli[ilk - 1]
        s_ilk = hucreli[ilk][0]
        if (len(hs_ust) >= 2 and not any(_hizali_sayi_mi(h.metin) for h in hs_ust)
                and s_ilk.top - s_ust.bottom <= 2.5 * s_ilk.yukseklik):
            baslik_no = ilk - 1

    # Sayı kolonları: ortak sağ kenar
    kolonlar: List[Dict] = []
    atanan: Dict[Tuple[int, int], int] = {}
    for e in kenarlar:
        kolonlar.append({"tur": "R", "capa": e, "x0": e, "x1": e})
    for no in blok:
        for j, h in enumerate(hucreli[no][1]):
            if not _hizali_sayi_mi(h.metin):
                continue
            for ki, kol in enumerate(kolonlar):
                if abs(h.x1 - kol["capa"]) <= KENAR_TOLERANSI:
                    kol["x0"] = min(kol["x0"], h.x0)
                    atanan[(no, j)] = ki
                    break

    # Metin kolonları: ortak sol kenar
    serbest = [(h.x0, (no, j)) for no in blok for j, h in enumerate(hucreli[no][1])
               if (no, j) not in atanan
               and not any(kol["x0"] - 1 <= (h.x0 + h.x1) / 2 <= kol["x1"] + 1 for kol in kolonlar)]
    for x, nolar in _kumele([(x, i) for i, (x, _) in enumerate(serbest)], HIZA_TOLERANSI):
        uyeler = [serbest[i][1] for i in nolar]
        genislik = max(hucreli[no][1][j].x1 for no, j in uyeler)
        kolonlar.append({"tur": "L", "capa": min(hucreli[no][1][j].x0 for no, j in uyeler),
                         "x0": min(hucreli[no][1][j].x0 for no, j in uyeler), "x1": genislik,
                         "uye": len({no for no, _ in uyeler})})
    # Tek hücrelik, başka kolonla çakışan sol kenar kümelerini komşusuna kat
    kolonlar = [k for k in kolonlar if not (
        k["tur"] == "L" and k["uye"] < 2 and len(blok) >= 3
        and any(d is not k and d["x0"] < k["x1"] and k["x0"] < d["x1"] for d in kolonlar))]
    kolonlar.sort(key=lambda k: k["x0"])
    if len(kolonlar) < 2:
        return None

    def kolon_bul(h: Hucre) -> int:
        for ki, kol in enumerate(kolonlar):
            if kol["tur"] == "R" and _hizali_sayi_mi(h.metin) and abs(h.x1 - kol["capa"]) <= KENAR_TOLERANSI:
                return ki
        for ki, kol in enumerate(kolonlar):
            if kol["tur"] == "R" and abs(h.x1 - kol["capa"]) <= KENAR_TOLERANSI:
                return ki
            if kol["tur"] == "L" and abs(h.x0 - kol["capa"]) <= HIZA_TOLERANSI:
                return ki
        ortusme = [(min(h.x1, kol["x1"]) - max(h.x0, kol["x0"]), ki) for ki, kol in enumerate(kolonlar)]
        en_iyi = max(ortusme)
        if en_iyi[0] > 0:
            return en_iyi[1]
        orta = (h.x0 + h.x1) / 2
        return min((abs(orta - (kol["x0"] + kol["x1"]) / 2), ki) for ki, kol in enumerate(kolonlar))[1]

    satir_nolari = ([baslik_no] if baslik_no is not None else []) + blok
    satirlar = []
    for no in satir_nolari:
        satir = [""] * len(kolonlar)
        for h in hucreli[no][1]:
            ki = kolon_bul(h)
            satir[ki] = (satir[ki] + " " + h.metin).strip()
        satirlar.append(satir)

    capalar = [(k["tur"], k["capa"]) for k in kolonlar]
    return Tablo(satirlar, capalar, sayfa_no, sayfa_no, hucreli[satir_nolari[0]][0].top)


def _ayni_duzen(a: Tablo, b: Tablo) -> bool:
    return len(a.capalar) == len(b.capalar) and all(
        ta == tb and abs(xa - xb) <= 3.0 for (ta, xa), (tb, xb) in zip(a.capalar, b.capalar))


def _norm(satir: List[str]) -> List[str]:
    return [sade(h) for h in satir]


def tablolari_birlestir(sayfa_tablolari: List[List[Tablo]]) -> List[Tablo]:
    """Sayfa sonunda biten tabloyla sonraki sayfanın başındaki aynı düzenli tabloyu birleştirir."""
    sonuc: List[Tablo] = []
    for tablolar in sayfa_tablolari:
        for i, t in enumerate(sorted(tablolar, key=lambda t: t.top)):
            ust = sonuc[-1] if sonuc else None
            if (i == 0 and ust is not None and ust.sayfa_son == t.sayfa_ilk - 1
                    and _ayni_duzen(ust, t)):
                ilk = t.satirlar[0]
                if _norm(ilk) == _norm(ust.satirlar[0]):
                    ust.satirlar.extend(t.satirlar[1:])     # tekrarlanan başlık atılır
                    ust.sayfa_son = t.sayfa_son
                    continue
                if not (basliga_benzer(ilk) and basliga_benzer(ust.satirlar[0])):
                    ust.satirlar.extend(t.satirlar)          # başlıksız devam
                    ust.sayfa_son = t.sayfa_son
                    continue
            sonuc.append(t)
    return sonuc


def _bos_kolonlari_at(satirlar: List[List[str]]) -> List[List[str]]:
    genislik = max(len(r) for r in satirlar)
    satirlar = [r + [""] * (genislik - len(r)) for r in satirlar]
    dolu = [j for j in range(genislik) if any(r[j] for r in satirlar)]
    return [[r[j] for j in dolu] for r in satirlar]


# ---------------------------------------------------------------------------
# Excel yazımı
# ---------------------------------------------------------------------------

def _hucre(ws, satir: int, sutun: int, deger, bicim: Optional[str] = None):
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
    c = ws.cell(row=satir, column=sutun)
    if isinstance(deger, str):
        c.value = ILLEGAL_CHARACTERS_RE.sub("", deger)
        c.data_type = "s"          # '=' ile başlayan metin formül sayılmasın
    else:
        c.value = deger
    if bicim:
        c.number_format = bicim
    return c


def _genislikleri_ayarla(ws, en_fazla: int = 60):
    from openpyxl.utils import get_column_letter
    for j, kolon in enumerate(ws.iter_cols(values_only=True), 1):
        uzunluk = max((len(str(v)) for v in kolon if v is not None), default=6)
        ws.column_dimensions[get_column_letter(j)].width = min(max(uzunluk + 2, 8), en_fazla)


def _kaydet(wb, hedef: str) -> str:
    klasor = os.path.dirname(os.path.abspath(hedef))
    gecici = os.path.join(klasor, f".~{os.getpid()}_{os.path.basename(hedef)}")
    try:
        wb.save(gecici)
        os.replace(gecici, hedef)
    except PermissionError:
        _sessizce_sil(gecici)
        raise KullaniciHatasi(
            f"Excel dosyası yazılamadı: {hedef}\n"
            "Dosya Excel'de açıksa kapatıp tekrar deneyin; klasöre yazma izni olduğundan emin olun.")
    except OSError as hata:
        _sessizce_sil(gecici)
        raise KullaniciHatasi(f"Excel dosyası yazılamadı: {hedef}\n({hata.strerror})")
    return os.path.abspath(hedef)


def _sessizce_sil(yol: str):
    try:
        os.remove(yol)
    except OSError:
        pass


def ekstre_excel(sonuc: EkstreSonucu, hedef: str) -> str:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "Ekstre"
    for j, baslik in enumerate(BASLIKLAR_EKSTRE, 1):
        _hucre(ws, 1, j, baslik).font = Font(bold=True)
    sari = PatternFill("solid", fgColor="FFF2CC")
    for i, h in enumerate(sonuc.hareketler, 2):
        _hucre(ws, i, 1, h.tarih, "DD.MM.YYYY")
        _hucre(ws, i, 2, " ".join(h.aciklama))
        _hucre(ws, i, 3, float(h.tutar), "#,##0.00")
        _hucre(ws, i, 4, float(h.bakiye), "#,##0.00")
        if h.kontrol:
            _hucre(ws, i, 5, h.kontrol).fill = sari
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:E{len(sonuc.hareketler) + 1}"
    _genislikleri_ayarla(ws, en_fazla=70)
    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["C"].width = ws.column_dimensions["D"].width = 16
    return _kaydet(wb, hedef)


def tablo_excel(tablolar: List[Tablo], hedef: str) -> str:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    wb.remove(wb.active)
    for no, tablo in enumerate(tablolar, 1):
        ws = wb.create_sheet(f"Tablo {no}")
        satirlar = _bos_kolonlari_at(tablo.satirlar)
        baslikli = basliga_benzer(satirlar[0])
        for i, satir in enumerate(satirlar, 1):
            for j, metin in enumerate(satir, 1):
                deger, bicim = (metin or None, None) if (i == 1 and baslikli) else hucre_degeri(metin)
                if deger is None:
                    continue
                c = _hucre(ws, i, j, deger, bicim)
                if i == 1 and baslikli:
                    c.font = Font(bold=True)
        if baslikli:
            ws.freeze_panes = "A2"
        _genislikleri_ayarla(ws)
    return _kaydet(wb, hedef)


# ---------------------------------------------------------------------------
# Akış
# ---------------------------------------------------------------------------

def cevir(pdf_yolu: str) -> Tuple[str, str]:
    """PDF'i çevirir → (Excel yolu, kullanıcıya özet)."""
    if not os.path.isfile(pdf_yolu):
        raise KullaniciHatasi(f"Dosya bulunamadı: {pdf_yolu}")
    try:
        import openpyxl  # noqa: F401
        import pdfplumber
        from pdfminer.pdfdocument import PDFPasswordIncorrect
    except ImportError:
        raise KullaniciHatasi(
            "Gerekli bileşenler (pdfplumber, openpyxl) kurulu değil. "
            "Programı 'Ekstre Çevir' simgesiyle çalıştırın; ilk açılışta kendisi kurar.")

    try:
        pdf = pdfplumber.open(pdf_yolu)
    except PDFPasswordIncorrect:
        raise KullaniciHatasi("Bu PDF parolayla korunuyor. Parolasız bir kopyasını kaydedip tekrar deneyin.")
    except Exception:
        raise KullaniciHatasi("Bu dosya açılamadı; geçerli bir PDF olmayabilir ya da bozuk olabilir.")

    kok = os.path.splitext(pdf_yolu)[0]
    with pdf:
        sayfa_kelimeleri_listesi = []
        for no, sayfa in enumerate(pdf.pages, 1):
            sayfa = sayfa.dedupe_chars()
            sayfa_kelimeleri_listesi.append((sayfa, sayfa_kelimeleri(sayfa)))
        if not any(k for _, k in sayfa_kelimeleri_listesi):
            raise KullaniciHatasi(
                "Bu PDF'te okunabilir metin yok; taranmış ya da fotoğraftan oluşturulmuş olabilir. "
                "Bu program yalnızca metni seçilebilen PDF'leri çevirebilir.")

        # 1-2) Banka ekstresi mi?
        sayfalar = [satirlara_ayir(k, no) for no, (_, k) in enumerate(sayfa_kelimeleri_listesi, 1)]
        ekstre = ekstre_coz(sayfalar)
        if ekstre.ekstre_mi:
            yol = ekstre_excel(ekstre, kok + "_ekstre.xlsx")
            notlu = sum(1 for h in ekstre.hareketler if h.kontrol)
            ozet = f"Banka ekstresi: {len(ekstre.hareketler)} hareket, {ekstre.dogrulanan} tanesi bakiyeyle doğrulandı."
            if notlu:
                ozet += f" {notlu} satırda Kontrol notu var."
            return yol, ozet

        # 3) Tablo modu
        sayfa_tablolari = []
        for no, (sayfa, kelimeler) in enumerate(sayfa_kelimeleri_listesi, 1):
            cizgili = cizgili_tablolar(sayfa, no)
            kutular = [kutu for _, kutu in cizgili]
            kalan = [k for k in kelimeler
                     if not any(x0 <= (k.x0 + k.x1) / 2 <= x1 and t <= (k.top + k.bottom) / 2 <= b
                                for x0, t, x1, b in kutular)]
            tablolar = [t for t, _ in cizgili] + cizgisiz_tablolar(satirlara_ayir(kalan, no), no)
            sayfa_tablolari.append(tablolar)
        tablolar = tablolari_birlestir(sayfa_tablolari)

    if not tablolar:
        raise KullaniciHatasi(
            "Bu belgede banka ekstresi ya da tablo bulunamadı; Excel dosyası oluşturulmadı.")
    yol = tablo_excel(tablolar, kok + "_tablo.xlsx")
    return yol, f"Ekstre değil, tablo modu kullanıldı: {len(tablolar)} tablo bulundu."


class _Ayristirici(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("Hata: PDF dosyasının yolunu verin. Örnek: ekstre_cevir.py --yol belge.pdf\n")
        sys.exit(1)


def main(argv=None) -> int:
    for akis in (sys.stdout, sys.stderr):
        try:
            akis.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ayr = _Ayristirici(prog="ekstre_cevir.py", description="PDF banka ekstresini Excel'e çevirir.")
    ayr.add_argument("--yol", action="store_true", help="yalnızca üretilen Excel dosyasının yolunu yaz")
    ayr.add_argument("pdf", help="çevrilecek PDF dosyası")
    args = ayr.parse_args(argv)

    try:
        yol, ozet = cevir(args.pdf)
    except KullaniciHatasi as hata:
        sys.stderr.write(f"{hata}\n")
        return 1
    except Exception as hata:  # beklenmeyen: yine anlaşılır bir mesaj ver
        sys.stderr.write(f"Beklenmeyen bir hata oluştu, belge çevrilemedi.\n({type(hata).__name__}: {hata})\n")
        return 1

    if args.yol:
        print(yol)
    else:
        print(ozet)
        print(f"Excel dosyası: {yol}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
