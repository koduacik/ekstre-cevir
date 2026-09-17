#!/usr/bin/env python3
"""Ekstre Çevir — PDF banka ekstresini ve PDF tablolarını Excel'e çevirir.

Kullanım:
    python ekstre_cevir.py belge.pdf [baska.pdf ...]
    python ekstre_cevir.py --yol belge.pdf      # yalnız üretilen dosya yolunu yazar

Önce belgeyi banka ekstresi olarak okumayı dener (tutarı bakiyeyle doğrular).
Ekstre değilse içindeki tabloları olduğu gibi aktarır.

Çıktı: <ad>_ekstre.xlsx  ya da  <ad>_tablo.xlsx
Hiçbir ağ çağrısı yapmaz; dosya diskten çıkmaz.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

TARIH = re.compile(r"^(\d{2})[./](\d{2})[./](\d{4})$")
# 1.234,56 · 1234,56 · -1.234,56 · 1.234,56-
SAYI = re.compile(r"^-?\d{1,3}(?:\.\d{3})*,\d{2}-?$|^-?\d+,\d{2}-?$")
ATLANACAK = ("DEVREDEN", "TOPLAM", "SAYFA", "HESAP", "SUBE", "IBAN", "TARIH ")


def sayiya(metin: str) -> float:
    """'1.234,56-' → -1234.56   ·   '-1.234,56' → -1234.56"""
    eksi = metin.startswith("-") or metin.endswith("-")
    temiz = metin.strip("-").replace(".", "").replace(",", ".")
    deger = float(temiz)
    return -deger if eksi else deger


@dataclass
class Hareket:
    tarih: str
    aciklama: str
    tutar: float | None = None
    bakiye: float | None = None
    kontrol: str = ""
    _tutar_x: float | None = field(default=None, repr=False)
    _isaretli: bool = field(default=False, repr=False)
    _aciklama_x: float | None = field(default=None, repr=False)
    _sayfa: int = field(default=-1, repr=False)


def satirlara_ayir(sayfa) -> list[list[dict]]:
    """Kelimeleri y konumuna göre satırlara toplar."""
    kelimeler = sayfa.extract_words(use_text_flow=False, keep_blank_chars=False)
    satirlar: dict[int, list[dict]] = {}
    for k in kelimeler:
        anahtar = round(k["top"] / 3)  # 3 puntoluk tolerans
        satirlar.setdefault(anahtar, []).append(k)
    return [sorted(s, key=lambda k: k["x0"]) for _, s in sorted(satirlar.items())]


def pdf_oku(yol: Path) -> list[Hareket]:
    hareketler: list[Hareket] = []
    with pdfplumber.open(yol) as pdf:
        for sayfa_no, sayfa in enumerate(pdf.pages):
            for satir in satirlara_ayir(sayfa):
                metinler = [k["text"] for k in satir]
                if not metinler:
                    continue
                ilk = metinler[0]

                if not TARIH.match(ilk):
                    # Tarihsiz satır, ancak AÇIKLAMA KOLONUYLA HİZALIYSA ve aynı
                    # sayfadaysa önceki hareketin devamıdır. Hizayı şart koşmazsan
                    # sayfa başlığı/altlığı önceki açıklamaya yapışır.
                    onceki = hareketler[-1] if hareketler else None
                    if (onceki is not None
                            and onceki._sayfa == sayfa_no
                            and onceki._aciklama_x is not None
                            and abs(satir[0]["x0"] - onceki._aciklama_x) < 5
                            and not any(SAYI.match(m) for m in metinler)
                            and not any(ilk.upper().startswith(a) for a in ATLANACAK)):
                        onceki.aciklama += " " + " ".join(metinler)
                    continue

                sayilar = [(k["text"], k["x1"]) for k in satir if SAYI.match(k["text"])]
                aciklama = " ".join(
                    k["text"] for k in satir[1:] if not SAYI.match(k["text"])
                ).strip()

                aciklama_kelimeleri = [k for k in satir[1:] if not SAYI.match(k["text"])]
                h = Hareket(
                    tarih=ilk,
                    aciklama=aciklama,
                    _aciklama_x=aciklama_kelimeleri[0]["x0"] if aciklama_kelimeleri else None,
                    _sayfa=sayfa_no,
                )
                if len(sayilar) >= 2:
                    ham_tutar, x = sayilar[-2]
                    h.tutar = sayiya(ham_tutar)
                    h._tutar_x = x
                    h._isaretli = ham_tutar.startswith("-") or ham_tutar.endswith("-")
                    h.bakiye = sayiya(sayilar[-1][0])
                elif len(sayilar) == 1:
                    h.bakiye = sayiya(sayilar[-1][0])
                    h.kontrol = "tutar okunamadı"
                else:
                    h.kontrol = "sayı bulunamadı"
                hareketler.append(h)
    return hareketler


def isaretleri_duzelt(hareketler: list[Hareket]) -> None:
    """İşareti yazılmamış tutarları BAKİYE FARKINDAN türetir ve doğrular.

    Bazı bankalar eksi işareti koymaz; borç/alacak ayrı kolondadır. Bakiye
    farkı hem işareti verir hem de okunan tutarı doğrular.
    """
    onceki: float | None = None
    for h in hareketler:
        if h.bakiye is None or h.tutar is None:
            onceki = h.bakiye if h.bakiye is not None else onceki
            continue
        if onceki is not None:
            fark = round(h.bakiye - onceki, 2)
            if abs(abs(fark) - abs(h.tutar)) < 0.01:
                if not h._isaretli:
                    h.tutar = fark          # işaret bakiyeden geldi
                elif abs(fark - h.tutar) > 0.01:
                    h.kontrol = "işaret bakiyeyle uyuşmuyor"
            else:
                h.kontrol = "tutar bakiyeyle uyuşmuyor"
        elif not h._isaretli:
            h.kontrol = "işaret belirsiz (ilk satır)"
        onceki = h.bakiye


def excele_yaz(hareketler: list[Hareket], hedef: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Ekstre"
    basliklar = ["Tarih", "Açıklama", "Tutar", "Bakiye", "Kontrol"]
    ws.append(basliklar)
    for h in hareketler:
        ws.append([h.tarih, h.aciklama, h.tutar, h.bakiye, h.kontrol])

    for h_ in ws[1]:
        h_.font = Font(bold=True)
    for satir in ws.iter_rows(min_row=2, min_col=3, max_col=4):
        for hucre in satir:
            hucre.number_format = "#,##0.00"
    ws.freeze_panes = "A2"
    for i, genislik in enumerate((12, 62, 14, 14, 26), start=1):
        ws.column_dimensions[get_column_letter(i)].width = genislik
    ws.column_dimensions["B"].alignment = Alignment(wrap_text=False)
    wb.save(hedef)


# ══ Ekstre mi? ═══════════════════════════════════════════════════════════════
TEMIZ_KONTROL = ("", "işaret belirsiz (ilk satır)")


def ekstre_mi(hareketler: list[Hareket]) -> bool:
    """Bakiye doğrulaması aynı zamanda ekstre dedektörüdür.

    Satırları tarihle başlayan her tablo ekstre değildir (ör. günlük satış raporu).
    Gerçek ekstrede satırların neredeyse hepsi bakiyeyle doğrulanır; doğrulanamıyorsa
    belge ekstre değildir ve tablo olarak aktarılmalıdır.
    """
    if len(hareketler) < 2:
        return False
    temiz = sum(1 for h in hareketler if h.kontrol in TEMIZ_KONTROL)
    return temiz / len(hareketler) >= 0.7


# ══ Tablo modu ═══════════════════════════════════════════════════════════════
TR_SAYI = re.compile(r"^-?\d{1,3}(?:\.\d{3})+(?:,\d+)?-?$|^-?\d+(?:,\d+)?-?$")
PARA_EKI = re.compile(r"\s*(?:TL|₺|TRY)$", re.IGNORECASE)


def hucre_degeri(metin: str):
    """'1.234,56' → 1234.56 · '120' → 120 · '1.250,00 TL' → 1250.0
    Baştaki sıfırlı kodlar ('0532…', '007') ve tarihler METİN kalır."""
    ham = (metin or "").replace("\n", " ").strip()
    aday = PARA_EKI.sub("", ham)
    if not TR_SAYI.match(aday):
        return ham
    eksi = aday.startswith("-") or aday.endswith("-")
    govde = aday.strip("-")
    tam = govde.split(",")[0].replace(".", "")
    if len(tam) > 1 and tam.startswith("0"):
        return ham
    if "," in govde:
        deger = float(govde.replace(".", "").replace(",", "."))
    else:
        deger = int(tam)
    return -deger if eksi else deger


def _sayi_mi(metin: str) -> bool:
    return bool(TR_SAYI.match(PARA_EKI.sub("", (metin or "").strip())))


def _temizle(tablo: list[list]) -> list[list[str]]:
    satirlar = [[(c or "").replace("\n", " ").strip() for c in r] for r in tablo]
    satirlar = [r for r in satirlar if any(r)]
    if not satirlar:
        return []
    genislik = max(len(r) for r in satirlar)
    satirlar = [r + [""] * (genislik - len(r)) for r in satirlar]
    dolu = [j for j in range(genislik) if any(r[j] for r in satirlar)]
    return [[r[j] for j in dolu] for r in satirlar]


def _cizgisiz_tablo(sayfa) -> list[list[str]] | None:
    """Kenarlıksız tablo: sağa hizalı sayıların ORTAK SAĞ KENARINDAN kolon çıkarır.

    Hazır metin stratejisi düz paragrafı da tablo sanıyor ve sola hizalı başlıkları
    sağa hizalı sayılarla eşleştiremiyor; bu yüzden kolonları konumdan kendimiz buluyoruz.
    """
    satirlar = satirlara_ayir(sayfa)
    sayili = [s for s in satirlar if any(_sayi_mi(k["text"]) for k in s)]
    if len(sayili) < 3:
        return None

    # sayısal kolonlar = sağ kenar kümeleri
    kenarlar = sorted(k["x1"] for s in sayili for k in s if _sayi_mi(k["text"]))
    kumeler: list[list[float]] = []
    for x in kenarlar:
        if kumeler and x - kumeler[-1][-1] <= 4:
            kumeler[-1].append(x)
        else:
            kumeler.append([x])
    esik = max(3, int(len(sayili) * 0.6))
    kolonlar = [sum(k) / len(k) for k in kumeler if len(k) >= esik]
    if not kolonlar:
        return None

    def kolona(x1):
        j = min(range(len(kolonlar)), key=lambda i: abs(kolonlar[i] - x1))
        return j if abs(kolonlar[j] - x1) <= 5 else None

    # veri satırı: sayılarının çoğu bir kolona oturuyor olmalı (altlık/sayfa no elenir)
    veri = []
    for s in sayili:
        sayilar = [k for k in s if _sayi_mi(k["text"])]
        oturan = sum(1 for k in sayilar if kolona(k["x1"]) is not None)
        if oturan and oturan / len(sayilar) >= 0.5:
            veri.append(s)
    if len(veri) < 3:
        return None

    sol_sinir = min(k["x0"] for s in veri for k in s
                    if _sayi_mi(k["text"]) and kolona(k["x1"]) is not None) - 2

    # soldaki metin kolonları: aralarında belirgin boşluk olan parça başlangıçları
    def parcalar(kelimeler):
        out = []
        for k in kelimeler:
            if out and k["x0"] - out[-1]["x1"] <= 8:
                out[-1]["text"] += " " + k["text"]
                out[-1]["x1"] = k["x1"]
            else:
                out.append({"text": k["text"], "x0": k["x0"], "x1": k["x1"]})
        return out

    baslangiclar = sorted(p["x0"] for s in veri for p in parcalar([k for k in s if k["x1"] <= sol_sinir]))
    metin_kumeleri: list[list[float]] = []
    for x in baslangiclar:
        if metin_kumeleri and x - metin_kumeleri[-1][-1] <= 6:
            metin_kumeleri[-1].append(x)
        else:
            metin_kumeleri.append([x])
    metin_kolonlari = [min(k) for k in metin_kumeleri if len(k) >= esik] or [min(baslangiclar)] if baslangiclar else []
    n_metin, n_sayi = len(metin_kolonlari), len(kolonlar)

    def satir_kur(kelimeler):
        hucre = [""] * (n_metin + n_sayi)
        for k in kelimeler:
            if _sayi_mi(k["text"]) and kolona(k["x1"]) is not None:
                j = n_metin + kolona(k["x1"])
                hucre[j] = (hucre[j] + " " + k["text"]).strip()
        for p in parcalar([k for k in kelimeler if not (_sayi_mi(k["text"]) and kolona(k["x1"]) is not None)]):
            if p["x1"] <= sol_sinir and metin_kolonlari:
                j = max((i for i in range(n_metin) if metin_kolonlari[i] <= p["x0"] + 6), default=0)
            else:
                j = n_metin + min(range(n_sayi), key=lambda i: abs(kolonlar[i] - p["x1"]))
            hucre[j] = (hucre[j] + " " + p["text"]).strip()
        return hucre

    tablo = [satir_kur(s) for s in veri]

    # başlık: ilk veri satırının hemen üstündeki, sayı içermeyen, en az 2 parçalı satır
    ilk = satirlar.index(veri[0])
    if ilk > 0:
        aday = satirlar[ilk - 1]
        if not any(_sayi_mi(k["text"]) for k in aday) and len(parcalar(aday)) >= 2 \
                and veri[0][0]["top"] - aday[0]["top"] < 30:
            # her kolonun [sol, sağ] aralığı. Metin kolonunun sağ sınırı, o kolondaki
            # en uzun GERÇEK verinin bittiği yerdir — sayıların başladığı yer değil;
            # yoksa sayı kolonunun sola hizalı başlığı metin kolonuna düşer.
            metin_sag = list(metin_kolonlari)
            for s_ in veri:
                for p_ in parcalar([k for k in s_ if k["x1"] <= sol_sinir and not _sayi_mi(k["text"])]):
                    i = max((i for i in range(n_metin) if metin_kolonlari[i] <= p_["x0"] + 6), default=0)
                    metin_sag[i] = max(metin_sag[i], p_["x1"])
            spanlar = [(metin_kolonlari[i], metin_sag[i]) for i in range(n_metin)]
            for i, x1 in enumerate(kolonlar):
                sol = min((k["x0"] for s in veri for k in s if _sayi_mi(k["text"]) and kolona(k["x1"]) == i), default=x1)
                spanlar.append((sol, x1))
            baslik = [""] * (n_metin + n_sayi)
            for p in parcalar(aday):
                orta = (p["x0"] + p["x1"]) / 2
                j = min(range(len(spanlar)), key=lambda i: 0 if spanlar[i][0] - 4 <= orta <= spanlar[i][1] + 4
                        else abs((spanlar[i][0] + spanlar[i][1]) / 2 - orta))
                # sola hizalı başlık iki metin kolonuna birden uzanabilir: kelime kelime dağıt
                if p["x1"] <= sol_sinir and n_metin > 1:
                    for k in [k for k in aday if p["x0"] - 1 <= k["x0"] and k["x1"] <= p["x1"] + 1]:
                        jj = max((i for i in range(n_metin) if metin_kolonlari[i] <= k["x0"] + 6), default=0)
                        baslik[jj] = (baslik[jj] + " " + k["text"]).strip()
                    continue
                baslik[j] = (baslik[j] + " " + p["text"]).strip()
            tablo.insert(0, baslik)
    return _temizle(tablo)


def _baslik_mi(satir: list[str]) -> bool:
    return any(satir) and not any(_sayi_mi(c) for c in satir if c)


def tablolari_oku(yol: Path) -> list[list[list[str]]]:
    """Önce çizgili tablolar (kesin), yoksa çizgisiz kolon çıkarımı.
    Sayfalara bölünmüş aynı tablo tek tabloda birleştirilir."""
    ham: list[list[list[str]]] = []
    with pdfplumber.open(yol) as pdf:
        for sayfa in pdf.pages:
            cizgili = [t for t in (_temizle(t) for t in sayfa.extract_tables()) if len(t) >= 2]
            if cizgili:
                ham.extend(cizgili)
            else:
                t = _cizgisiz_tablo(sayfa)
                if t and len(t) >= 2:
                    ham.append(t)

    birlesik: list[list[list[str]]] = []
    for t in ham:
        onceki = birlesik[-1] if birlesik else None
        if onceki and len(onceki[0]) == len(t[0]):
            if t[0] == onceki[0]:                      # başlık sayfada tekrarlanmış
                onceki.extend(t[1:])
                continue
            if _baslik_mi(onceki[0]) and not _baslik_mi(t[0]):   # başlıksız devam sayfası
                onceki.extend(t)
                continue
        birlesik.append([list(r) for r in t])
    return birlesik


def excele_yaz_tablo(tablolar: list[list[list[str]]], hedef: Path) -> None:
    wb = Workbook()
    wb.remove(wb.active)
    for no, tablo in enumerate(tablolar, start=1):
        ws = wb.create_sheet(f"Tablo {no}")
        baslikli = _baslik_mi(tablo[0])
        for i, satir in enumerate(tablo):
            ws.append(satir if (i == 0 and baslikli) else [hucre_degeri(c) for c in satir])
        if baslikli:
            for h in ws[1]:
                h.font = Font(bold=True)
            ws.freeze_panes = "A2"
        genislikler: dict[int, int] = {}
        for satir in ws.iter_rows():
            for h in satir:
                if isinstance(h.value, float):
                    h.number_format = "#,##0.00"
                elif isinstance(h.value, int):
                    h.number_format = "#,##0"
                genislikler[h.column] = max(genislikler.get(h.column, 0), len(str(h.value or "")))
        for sutun, g in genislikler.items():
            ws.column_dimensions[get_column_letter(sutun)].width = min(60, max(9, g + 2))
    wb.save(hedef)


# ══ Karar ════════════════════════════════════════════════════════════════════
class BelgeOkunamadi(Exception):
    """Ne ekstre ne tablo bulunabildi."""


EkstreBulunamadi = BelgeOkunamadi   # eski ad


def cevir(yol: Path) -> tuple[Path, str, str]:
    """→ (üretilen dosya, 'ekstre' | 'tablo', insan için özet)"""
    hareketler = pdf_oku(yol)
    isaretleri_duzelt(hareketler)
    if ekstre_mi(hareketler):
        hedef = yol.with_name(yol.stem + "_ekstre.xlsx")
        excele_yaz(hareketler, hedef)
        sorunlu = sum(1 for h in hareketler if h.kontrol)
        ozet = f"ekstre · {len(hareketler)} hareket"
        if sorunlu:
            ozet += f", {sorunlu} satır kontrol gerektiriyor"
        return hedef, "ekstre", ozet

    tablolar = tablolari_oku(yol)
    if tablolar:
        hedef = yol.with_name(yol.stem + "_tablo.xlsx")
        excele_yaz_tablo(tablolar, hedef)
        satir = sum(len(t) - (1 if _baslik_mi(t[0]) else 0) for t in tablolar)
        return hedef, "tablo", f"tablo · {len(tablolar)} tablo, {satir} satır"

    # Boş Excel üretip "başarılı" demek, kullanıcıya bozuk program gibi görünür.
    raise BelgeOkunamadi(
        "Bu PDF'te ekstre ya da tablo bulunamadı. "
        "Taranmış (fotoğraf) bir PDF ya da yalnız yazıdan oluşan bir belge olabilir.")


def main(argv: list[str]) -> int:
    argumanlar = [a for a in argv[1:] if a != "--yol"]
    yalniz_yol = "--yol" in argv[1:]
    if not argumanlar:
        print(__doc__)
        return 1
    hata = False
    for arg in argumanlar:
        yol = Path(arg)
        if not yol.exists():
            print(f"✗ bulunamadı: {yol}", file=sys.stderr)
            hata = True
            continue
        try:
            hedef, _, ozet = cevir(yol)
        except BelgeOkunamadi as h:
            print(f"✗ {yol.name}: {h}", file=sys.stderr)
            hata = True
            continue
        if yalniz_yol:
            print(f"✓ {hedef.name}  ({ozet})", file=sys.stderr)
            print(hedef)
        else:
            print(f"✓ {hedef.name}  ({ozet})")
    return 1 if hata else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
