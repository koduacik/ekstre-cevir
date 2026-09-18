"""Bütün test belgelerini üretir.

    python tests/ornek_uret.py [klasör]      # varsayılan: tests/ornekler
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ornek_ekstre  # noqa: E402
import ornek_tablo  # noqa: E402


def hepsini_uret(klasor):
    """→ {ad: {'tur': 'ekstre'|'tablo'|'hata', 'pdf': yol, 'beklenen': [csv yolları]}}"""
    os.makedirs(klasor, exist_ok=True)
    liste = {}
    for ad in ornek_ekstre.DUZENLER:
        pdf, csv_yolu = ornek_ekstre.ekstre_uret(ad, klasor)
        liste[ad] = {"tur": "ekstre", "pdf": pdf, "beklenen": [csv_yolu]}
    for ad, uretici in ornek_tablo.URETICILER.items():
        pdf, csvler = uretici(klasor)
        liste[ad] = {"tur": "tablo" if csvler else "hata", "pdf": pdf, "beklenen": csvler}
    return liste


if __name__ == "__main__":
    hedef = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "ornekler")
    for ad, bilgi in hepsini_uret(hedef).items():
        print("{:32s} {:7s} {}".format(ad, bilgi["tur"], bilgi["pdf"]))
