#!/usr/bin/env python3
"""Doğruluk testi: üretilen PDF'ler ile gerçek veriyi karşılaştırır."""
from __future__ import annotations
import sys
from pathlib import Path

BURADA = Path(__file__).parent
sys.path.insert(0, str(BURADA.parent))
from ekstre_cevir import pdf_oku, isaretleri_duzelt  # noqa: E402


def gercegi_oku(yol: Path):
    satirlar = []
    for satir in yol.read_text(encoding="utf-8").splitlines()[1:]:
        tarih, acik, tutar, bakiye = satir.split(";")
        satirlar.append((tarih, acik, float(tutar), float(bakiye)))
    return satirlar


def main() -> int:
    toplam_hata = 0
    for ad in ("a", "b", "c"):
        gercek = gercegi_oku(BURADA / f"gercek_{ad}.csv")
        okunan = pdf_oku(BURADA / f"ornek_duzen_{ad}.pdf")
        isaretleri_duzelt(okunan)
        okunan = [h for h in okunan if "DEVREDEN" not in h.aciklama.upper()]

        hatalar = []
        if len(okunan) != len(gercek):
            hatalar.append(f"satır sayısı {len(okunan)} ≠ {len(gercek)}")
        for i, (g, o) in enumerate(zip(gercek, okunan), start=1):
            if o.tarih != g[0]:
                hatalar.append(f"satır {i}: tarih {o.tarih} ≠ {g[0]}")
            if o.tutar is None or abs(o.tutar - g[2]) > 0.01:
                hatalar.append(f"satır {i}: tutar {o.tutar} ≠ {g[2]}")
            if o.bakiye is None or abs(o.bakiye - g[3]) > 0.01:
                hatalar.append(f"satır {i}: bakiye {o.bakiye} ≠ {g[3]}")
            if not g[1].startswith(o.aciklama[:20]):
                hatalar.append(f"satır {i}: açıklama '{o.aciklama[:28]}' ≠ '{g[1][:28]}'")

        dogru = len(gercek) - len({h.split(":")[0] for h in hatalar if h.startswith("satır")})
        oran = 100 * dogru / len(gercek) if gercek else 0
        isaretli = sum(1 for h in okunan if h.kontrol)
        print(f"düzen {ad}: {dogru}/{len(gercek)} satır tam doğru (%{oran:.1f}) · "
              f"{isaretli} satır kontrol işaretli")
        for h in hatalar[:6]:
            print("   ·", h)
        if len(hatalar) > 6:
            print(f"   · … {len(hatalar)-6} hata daha")
        toplam_hata += len(hatalar)
    print("\nSONUÇ:", "TEMİZ" if toplam_hata == 0 else f"{toplam_hata} uyuşmazlık")
    return 0 if toplam_hata == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
