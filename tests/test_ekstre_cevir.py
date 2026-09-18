"""Ekstre Çevir uçtan uca testleri.

    .venv/bin/python -m unittest discover -s tests -v

Her çalıştırmada sahte belgeler geçici bir klasöre yeniden üretilir, program
gerçek komut satırıyla (--yol) çalıştırılır ve Excel çıktısı beklenen CSV'lerle
hücre hücre karşılaştırılır. Klasörü incelemek için: EKSTRE_TEST_SAKLA=1
"""
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal

import openpyxl

TEST_KLASORU = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(TEST_KLASORU)
PROGRAM = os.path.join(KOK, "ekstre_cevir.py")
sys.path.insert(0, TEST_KLASORU)
sys.path.insert(0, KOK)

from ornek_uret import hepsini_uret  # noqa: E402
from ortak import csv_oku  # noqa: E402

KONTROL_BEKLENEN = {
    "UYUMSUZ": ["Bakiye tutmuyor"],
    "ILK_DOGRULANAMADI": ["İlk hareket: önceki bakiye yok, tutar doğrulanamadı"],
    "ILK_KOLONDAN": ["İlk hareket: önceki bakiye yok, tutar doğrulanamadı", "işaret kolon konumundan alındı"],
    "ILK_ISARET_YOK": ["İlk hareket: önceki bakiye yok, işaret türetilemedi"],
}

KLASOR = None
LISTE = {}


def setUpModule():
    global KLASOR, LISTE
    KLASOR = tempfile.mkdtemp(prefix="ekstre_cevir_test_")
    LISTE = hepsini_uret(KLASOR)


def tearDownModule():
    if os.environ.get("EKSTRE_TEST_SAKLA"):
        print("\nTest belgeleri:", KLASOR)
    else:
        shutil.rmtree(KLASOR, ignore_errors=True)


def calistir(*argumanlar):
    return subprocess.run([sys.executable, PROGRAM] + list(argumanlar),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _metin(b):
    return b.decode("utf-8")


def _sayi_mi(deger):
    # Excel'e 11052.0 yazılan değer geri okunurken int dönebilir; ikisi de sayıdır.
    return isinstance(deger, (int, float)) and not isinstance(deger, bool)


def _kurus(deger, basamak=2):
    return Decimal(repr(deger)).quantize(Decimal(1).scaleb(-basamak))


class EkstreTestleri(unittest.TestCase):

    def _dogrula(self, ad):
        bilgi = LISTE[ad]
        sonuc = calistir("--yol", bilgi["pdf"])
        self.assertEqual(sonuc.returncode, 0, _metin(sonuc.stderr))
        beklenen_yol = os.path.abspath(os.path.splitext(bilgi["pdf"])[0] + "_ekstre.xlsx")
        self.assertEqual(_metin(sonuc.stdout), beklenen_yol + "\n", "--yol yalnızca dosya yolunu yazmalı")
        self.assertTrue(os.path.isfile(beklenen_yol))
        self.assertFalse(os.path.exists(os.path.splitext(bilgi["pdf"])[0] + "_tablo.xlsx"))

        ws = openpyxl.load_workbook(beklenen_yol)["Ekstre"]
        satirlar = list(ws.iter_rows(values_only=True))
        beklenen = csv_oku(bilgi["beklenen"][0])[1:]
        self.assertEqual(list(satirlar[0]), ["Tarih", "Açıklama", "Tutar", "Bakiye", "Kontrol"])
        self.assertEqual(len(satirlar) - 1, len(beklenen), "hareket sayısı")

        hatalar = []
        for no, (gercek, (tarih, aciklama, tutar, bakiye, kontrol)) in enumerate(zip(satirlar[1:], beklenen), 2):
            g_tarih, g_aciklama, g_tutar, g_bakiye, g_kontrol = gercek
            if g_tarih is None or g_tarih.strftime("%d.%m.%Y") != tarih:
                hatalar.append((no, "Tarih", tarih, g_tarih))
            if g_aciklama != aciklama:
                hatalar.append((no, "Açıklama", aciklama, g_aciklama))
            if not _sayi_mi(g_tutar) or _kurus(g_tutar) != Decimal(tutar):
                hatalar.append((no, "Tutar", tutar, g_tutar))
            if not _sayi_mi(g_bakiye) or _kurus(g_bakiye) != Decimal(bakiye):
                hatalar.append((no, "Bakiye", bakiye, g_bakiye))
            if not kontrol:
                if g_kontrol is not None:
                    hatalar.append((no, "Kontrol", "(boş)", g_kontrol))
            else:
                parcalar = KONTROL_BEKLENEN[kontrol]
                if (not isinstance(g_kontrol, str) or not g_kontrol.startswith(parcalar[0])
                        or not all(p in g_kontrol for p in parcalar)):
                    hatalar.append((no, "Kontrol", kontrol, g_kontrol))
        self.assertEqual(hatalar, [], "\n".join("satır {} {}: beklenen {!r}, çıkan {!r}".format(*h) for h in hatalar[:15]))
        return satirlar, beklenen

    def test_eksi_basta(self):
        _, beklenen = self._dogrula("ekstre_eksi_basta")
        # Kurgu gerçekten sınanıyor mu: iki satıra bölünen açıklama ve uyumsuz satır olmalı
        self.assertTrue(any(k == "UYUMSUZ" for *_, k in beklenen))

    def test_eksi_sonda(self):
        _, beklenen = self._dogrula("ekstre_eksi_sonda")
        self.assertTrue(any(Decimal(b) < 0 for _, _, _, b, _ in beklenen), "eksi bakiye de sınanmalı")

    def test_borc_alacak_ayri_kolon(self):
        _, beklenen = self._dogrula("ekstre_borc_alacak")
        self.assertEqual(beklenen[0][4], "ILK_KOLONDAN")
        self.assertTrue(any(k == "UYUMSUZ" for *_, k in beklenen))

    def test_en_yeni_hareket_ustte(self):
        _, beklenen = self._dogrula("ekstre_ters_sirali")
        self.assertEqual(beklenen[-1][4], "ILK_DOGRULANAMADI")

    def test_ilk_satir_isareti_turetilemiyor(self):
        _, beklenen = self._dogrula("ekstre_ilk_isaret_yok")
        self.assertEqual(beklenen[0][4], "ILK_ISARET_YOK")


class TabloTestleri(unittest.TestCase):

    def _dogrula(self, ad):
        bilgi = LISTE[ad]
        sonuc = calistir("--yol", bilgi["pdf"])
        self.assertEqual(sonuc.returncode, 0, _metin(sonuc.stderr))
        beklenen_yol = os.path.abspath(os.path.splitext(bilgi["pdf"])[0] + "_tablo.xlsx")
        self.assertEqual(_metin(sonuc.stdout), beklenen_yol + "\n")
        self.assertFalse(os.path.exists(os.path.splitext(bilgi["pdf"])[0] + "_ekstre.xlsx"),
                         "tablo belgesi ekstre sanılmamalı")

        wb = openpyxl.load_workbook(beklenen_yol)
        self.assertEqual(wb.sheetnames, ["Tablo {}".format(i) for i in range(1, len(bilgi["beklenen"]) + 1)])
        for ws, csv_yolu in zip(wb.worksheets, bilgi["beklenen"]):
            beklenen = csv_oku(csv_yolu)
            genislik = len(beklenen[0])
            self.assertEqual(ws.max_column, genislik, "{}: kolon sayısı".format(ws.title))
            satirlar = list(ws.iter_rows(values_only=True))
            self.assertEqual(len(satirlar), len(beklenen), "{}: satır sayısı".format(ws.title))
            hatalar = []
            for i, (gercek, bek) in enumerate(zip(satirlar, beklenen), 1):
                for j, (g, b) in enumerate(zip(gercek, bek), 1):
                    if not self._hucre_uyar(g, b):
                        hatalar.append((ws.title, i, j, b, g))
            self.assertEqual(hatalar, [], "\n".join("{} satır {} kolon {}: beklenen {!r}, çıkan {!r}".format(*h)
                                                    for h in hatalar[:15]))

    @staticmethod
    def _hucre_uyar(gercek, beklenen):
        if beklenen == "":
            return gercek is None
        tur, deger = beklenen.split(":", 1)
        if tur == "s":
            return isinstance(gercek, str) and gercek == deger
        if not _sayi_mi(gercek):
            return False
        basamak = len(deger.split(".")[1]) if "." in deger else 0
        return _kurus(gercek, basamak) == Decimal(deger)

    def test_kenarlikli_tablo(self):
        self._dogrula("tablo_kenarlikli")

    def test_sayfalara_bolunmus_tablo(self):
        self._dogrula("tablo_bolunmus")

    def test_kenarsiz_tablo(self):
        self._dogrula("tablo_kenarsiz")

    def test_tarihle_baslayan_satis_raporu(self):
        self._dogrula("tablo_satis_raporu")


class HataTestleri(unittest.TestCase):

    def _hata_bekle(self, pdf, ifade):
        sonuc = calistir("--yol", pdf)
        self.assertEqual(sonuc.returncode, 1)
        self.assertEqual(sonuc.stdout, b"", "hata durumunda yol yazılmamalı")
        self.assertIn(ifade, _metin(sonuc.stderr))
        self.assertEqual(glob.glob(os.path.splitext(pdf)[0] + "_*.xlsx"), [], "boş Excel üretilmemeli")

    def test_yalniz_paragraf(self):
        self._hata_bekle(LISTE["paragraf"]["pdf"], "banka ekstresi ya da tablo bulunamadı")

    def test_metinsiz_pdf(self):
        self._hata_bekle(LISTE["metinsiz"]["pdf"], "okunabilir metin yok")

    def test_olmayan_dosya(self):
        self._hata_bekle(os.path.join(KLASOR, "yok.pdf"), "Dosya bulunamadı")

    def test_pdf_olmayan_dosya(self):
        yol = os.path.join(KLASOR, "sahte.pdf")
        with open(yol, "w") as f:
            f.write("bu bir PDF değil")
        self._hata_bekle(yol, "açılamadı")

    def test_arguman_yok(self):
        self.assertEqual(calistir().returncode, 1)


class BirimTestleri(unittest.TestCase):

    def test_ekstre_sayilari(self):
        import ekstre_cevir as e
        self.assertEqual(e.ekstre_sayisi("1.234,56"), (Decimal("1234.56"), None))
        self.assertEqual(e.ekstre_sayisi("-1.234,56"), (Decimal("1234.56"), "-"))
        self.assertEqual(e.ekstre_sayisi("1.234,56-"), (Decimal("1234.56"), "-"))
        self.assertEqual(e.ekstre_sayisi("163,26"), (Decimal("163.26"), None))
        self.assertIsNone(e.ekstre_sayisi("-1,00-"))
        self.assertIsNone(e.ekstre_sayisi("12.03.2026"))

    def test_hucre_degerleri(self):
        import ekstre_cevir as e
        self.assertEqual(e.hucre_degeri("1.234,56")[0], 1234.56)
        self.assertEqual(e.hucre_degeri("1.250,00 TL")[0], 1250.0)
        self.assertEqual(e.hucre_degeri("0532 000 00 00")[0], "0532 000 00 00")
        self.assertEqual(e.hucre_degeri("05320000000")[0], "05320000000")
        self.assertEqual(e.hucre_degeri("01.03.2026")[0], "01.03.2026")
        self.assertEqual(e.hucre_degeri("=TOPLA(A1)")[0], "=TOPLA(A1)")

    def test_formul_gibi_metin_formul_olmaz(self):
        import ekstre_cevir as e
        wb = openpyxl.Workbook()
        c = e._hucre(wb.active, 1, 1, "=HYPERLINK(\"x\")")
        self.assertEqual(c.data_type, "s")


if __name__ == "__main__":
    unittest.main()
