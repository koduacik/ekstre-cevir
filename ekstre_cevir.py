#!/usr/bin/env python3
"""Ekstre Çevir — PDF banka ekstresini Excel'e çevirir.

Kullanım:
    python ekstre_cevir.py ekstre.pdf [baska.pdf ...]

Çıktı: her PDF için <ad>_ekstre.xlsx
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


class EkstreBulunamadi(Exception):
    """PDF'te tarihle başlayan hareket satırı yok — muhtemelen ekstre değil."""


def cevir(yol: Path) -> tuple[Path, int, int]:
    hareketler = pdf_oku(yol)
    if not hareketler:
        # Boş Excel üretip "başarılı" demek, kullanıcıya bozuk program gibi görünür.
        raise EkstreBulunamadi(
            "Bu PDF'te ekstre satırı bulunamadı (tarihle başlayan hareket yok). "
            "Taranmış bir PDF ya da banka ekstresi olmayan bir belge olabilir.")
    isaretleri_duzelt(hareketler)
    hedef = yol.with_name(yol.stem + "_ekstre.xlsx")
    excele_yaz(hareketler, hedef)
    sorunlu = sum(1 for h in hareketler if h.kontrol)
    return hedef, len(hareketler), sorunlu


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    hata = False
    for arg in argv[1:]:
        yol = Path(arg)
        if not yol.exists():
            print(f"✗ bulunamadı: {yol}", file=sys.stderr)
            hata = True
            continue
        try:
            hedef, adet, sorunlu = cevir(yol)
        except EkstreBulunamadi as h:
            print(f"✗ {yol.name}: {h}", file=sys.stderr)
            hata = True
            continue
        durum = f"{adet} hareket"
        if sorunlu:
            durum += f", {sorunlu} satır kontrol gerektiriyor"
        print(f"✓ {hedef.name}  ({durum})")
    return 1 if hata else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
