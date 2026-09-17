#!/usr/bin/env python3
"""docs/demo.gif + docs/demo.mp4 üretir.

EKRAN KAYDI DEĞİL — gerçek parçalardan kare kare üretilir:
  · PDF görüntüsü : test/ornek_duzen_a.pdf'in gerçek render'ı ("test amaçlı üretilmiştir")
  · Tablo hücreleri: calistir.sh'nin o anda ürettiği gerçek .xlsx dosyasından okunur
  · Simge         : docs/simge.png (Ekstre Çevir.app'in simgesi)
  · İşlem süresi  : calistir.sh bu betik içinde ÖLÇÜLÜR; animasyon asla gerçekten hızlı gösterilmez
"""
from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pypdfium2 as pdfium
from openpyxl import load_workbook
from PIL import Image, ImageDraw, ImageFont

KOK = Path(__file__).resolve().parent.parent
S = 2                      # süper örnekleme — kenarlar ve yazılar temiz çıksın
W, H = 800, 480
FPS = 15
SURE = 8.0

MASA = (219, 226, 233)
MUREKKEP = (14, 26, 39)
AMBER = (255, 176, 32)
BEYAZ = (255, 255, 255)
CIZGI = (212, 219, 226)
GRI = (96, 112, 128)
KIRMIZI = (181, 58, 44)

ARIAL = "/System/Library/Fonts/Supplemental/Arial.ttf"
ARIAL_K = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
AVENIR = "/System/Library/Fonts/Avenir Next.ttc"


def y(boy, kalin=False):
    return ImageFont.truetype(ARIAL_K if kalin else ARIAL, int(boy * S))


def av(boy, yuz):  # yuz: 8=Heavy, 5=Medium, 2=Demi Bold
    return ImageFont.truetype(AVENIR, int(boy * S), index=yuz)


def s(*v):
    return tuple(int(round(x * S)) for x in v)


def yumusak(t):  # easeInOutCubic
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def tl(x):
    if x is None:
        return ""
    t = f"{abs(x):,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")
    return ("-" if x < 0 else "") + t


def kes(ciz, metin, font, genislik):
    if ciz.textlength(metin, font=font) <= genislik:
        return metin
    while metin and ciz.textlength(metin + "…", font=font) > genislik:
        metin = metin[:-1]
    return metin + "…"


# ── gerçek veriyi üret ve süreyi ölç ─────────────────────────────────────────
def gercek_calistir():
    gecici = Path(tempfile.mkdtemp())
    pdf = gecici / "Ekstre Eylül.pdf"
    shutil.copy(KOK / "test" / "ornek_duzen_a.pdf", pdf)
    subprocess.run([str(KOK / "calistir.sh"), str(pdf)], check=True, capture_output=True)  # ısınma
    (gecici / "Ekstre Eylül_ekstre.xlsx").unlink()
    bas = time.perf_counter()
    cikti = subprocess.run([str(KOK / "calistir.sh"), str(pdf)], check=True,
                           capture_output=True, text=True).stdout.strip().splitlines()[-1]
    olculen = time.perf_counter() - bas
    satirlar = list(load_workbook(cikti).active.iter_rows(values_only=True))
    return pdf, satirlar, olculen


# ── katmanlar ────────────────────────────────────────────────────────────────
def pencere(w, h, baslik):
    im = Image.new("RGBA", s(w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, *s(w - 1, h - 1)), radius=10 * S, fill=BEYAZ, outline=(190, 199, 208), width=S)
    d.rounded_rectangle((0, 0, *s(w - 1, 26)), radius=10 * S, fill=(236, 239, 242))
    d.rectangle((0, *s(14, w - 1, 26)), fill=(236, 239, 242))
    d.line((0, *s(26, w, 26)), fill=CIZGI, width=S)
    for i, renk in enumerate([(255, 95, 87), (254, 188, 46), (40, 200, 64)]):
        cx, cy = 14 + i * 18, 13
        d.ellipse(s(cx - 6, cy - 6, cx + 6, cy + 6), fill=renk)
    f = y(12, True)
    tw = d.textlength(baslik, font=f)
    d.text(((w * S - tw) / 2, 6 * S), baslik, font=f, fill=(60, 70, 80))
    return im


def pdf_penceresi(pdf):
    w, h = 450, 440
    im = pencere(w, h, "Ekstre Eylül.pdf")
    sayfa = pdfium.PdfDocument(str(pdf))[0]
    olcek = (w - 2) * S / sayfa.get_width()
    goruntu = sayfa.render(scale=olcek).to_pil().convert("RGB")
    goruntu = goruntu.crop((0, 0, goruntu.width, (h - 28) * S))
    im.paste(goruntu, s(1, 27))
    return im


def tablo_penceresi(satirlar):
    w, h = 700, 412
    im = pencere(w, h, "Ekstre Eylül_ekstre.xlsx")
    d = ImageDraw.Draw(im)
    kolonlar = [("", 32), ("A", 86), ("B", 238), ("C", 96), ("D", 100), ("E", 148)]
    x0, ust = 0, 27
    f, fk, fh = y(12), y(12, True), y(11)
    # harf satırı
    x = x0
    for harf, gen in kolonlar:
        d.rectangle(s(x, ust, x + gen, ust + 20), fill=(243, 245, 247), outline=CIZGI)
        tw = d.textlength(harf, font=fh)
        d.text((s(x)[0] + (gen * S - tw) / 2, s(0, ust + 4)[1]), harf, font=fh, fill=GRI)
        x += gen
    satir_y = ust + 20
    sagda = {3, 4}
    for no, veri in enumerate(satirlar[:15], start=1):
        baslik = no == 1
        isaretli = not baslik and bool(veri[4])
        x = x0
        hucreler = [str(no)] + [
            (tl(v) if (i in (2, 3) and not baslik) else ("" if v is None else str(v)))
            for i, v in enumerate(veri)
        ]
        for i, ((_, gen), metin) in enumerate(zip(kolonlar, hucreler)):
            dolgu = (243, 245, 247) if i == 0 else ((255, 241, 204) if isaretli else BEYAZ)
            d.rectangle(s(x, satir_y, x + gen, satir_y + 24), fill=dolgu, outline=CIZGI)
            font = fk if (baslik or (isaretli and i == 5)) else (fh if i == 0 else f)
            renk = GRI if i == 0 else MUREKKEP
            if not baslik and i == 3 and metin.startswith("-"):
                renk = KIRMIZI
            if isaretli and i == 5:
                renk = (138, 90, 0)
            metin = kes(d, metin, font, (gen - 10) * S)
            tw = d.textlength(metin, font=font)
            if i == 0:
                tx = s(x)[0] + (gen * S - tw) / 2
            elif i in sagda and not baslik:
                tx = s(x + gen - 6)[0] - tw
            else:
                tx = s(x + 6)[0]
            d.text((tx, s(0, satir_y + 6)[1]), metin, font=font, fill=renk)
            x += gen
        satir_y += 24
        if satir_y + 24 > h - 2:
            break
    return im


def dosya_simgesi(etiket=True, secili=False):
    im = Image.new("RGBA", s(120, 110), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x0, y0, gw, gh = 33, 2, 54, 68
    d.polygon([s(x0, y0), s(x0 + gw - 16, y0), s(x0 + gw, y0 + 16), s(x0 + gw, y0 + gh), s(x0, y0 + gh)],
              fill=BEYAZ, outline=(170, 178, 186))
    d.polygon([s(x0 + gw - 16, y0), s(x0 + gw - 16, y0 + 16), s(x0 + gw, y0 + 16)], fill=(222, 227, 232))
    d.rectangle(s(x0, y0 + 40, x0 + gw, y0 + 56), fill=(208, 48, 40))
    fk = y(11, True)
    tw = d.textlength("PDF", font=fk)
    d.text((s(x0)[0] + (gw * S - tw) / 2, s(0, y0 + 42)[1]), "PDF", font=fk, fill=BEYAZ)
    if etiket:
        ad = "Ekstre Eylül.pdf"
        fl = y(12, secili)
        tw = d.textlength(ad, font=fl)
        if secili:
            d.rounded_rectangle(((120 * S - tw) / 2 - 5 * S, s(0, 76)[1], (120 * S + tw) / 2 + 5 * S, s(0, 94)[1]),
                                radius=4 * S, fill=(40, 110, 220))
        d.text(((120 * S - tw) / 2, s(0, 78)[1]), ad, font=fl, fill=BEYAZ if secili else MUREKKEP)
    return im


def uygulama_simgesi(vurgu=False, olcek=1.0):
    boy = 92
    simge = Image.open(KOK / "docs" / "simge.png").convert("RGBA").resize(s(boy, boy), Image.LANCZOS)
    im = Image.new("RGBA", s(130, 130), (0, 0, 0, 0))
    if vurgu:
        ImageDraw.Draw(im).rounded_rectangle(s(12, 2, 118, 108), radius=14 * S, fill=(14, 26, 39, 55))
    if olcek != 1.0:
        yeni = int(boy * S * olcek)
        simge = simge.resize((yeni, yeni), Image.LANCZOS)
    im.alpha_composite(simge, ((130 * S - simge.width) // 2, (110 * S - simge.height) // 2))
    d = ImageDraw.Draw(im)
    fl = y(12, True)
    tw = d.textlength("Ekstre Çevir", font=fl)
    d.text(((130 * S - tw) / 2, s(0, 108)[1]), "Ekstre Çevir", font=fl, fill=MUREKKEP)
    return im


def imlec(ciz, x, yy, basili=False):
    b = 1.35
    nokta = [(0, 0), (0, 17), (4.2, 13.2), (7, 19.6), (10, 18.4), (7.3, 12), (12.4, 12)]
    p = [s(x + px * b, yy + py * b) for px, py in nokta]
    ciz.polygon(p, fill=(0, 0, 0), outline=BEYAZ, width=int(1.6 * S))
    if basili:
        ciz.ellipse(s(x - 9, yy - 9, x + 9, yy + 9), outline=(40, 110, 220), width=2 * S)


def kapanis():
    im = Image.new("RGBA", s(W, H), MUREKKEP + (255,))
    d = ImageDraw.Draw(im)
    simge = Image.open(KOK / "docs" / "simge.png").convert("RGBA").resize(s(96, 96), Image.LANCZOS)
    # simgenin koyu zemini kartla birleşmesin: ince açık çerçeve
    d.rounded_rectangle(((W * S - s(104)[0]) // 2, s(0, 88)[1], (W * S + s(104)[0]) // 2, s(0, 192)[1]),
                        radius=24 * S, fill=(34, 52, 72))
    im.alpha_composite(simge, ((W * S - simge.width) // 2, s(0, 92)[1]))
    for metin, font, renk, yy in [
        ("Ekstre Çevir", av(46, 8), AMBER, 212),
        ("PDF banka ekstresinden Excel'e  ·  ücretsiz", av(22, 5), (242, 245, 248), 282),
        ("ozy2.com/programivar/ekstre-cevir", av(20, 2), (147, 167, 188), 326),
    ]:
        tw = d.textlength(metin, font=font)
        d.text(((W * S - tw) / 2, s(0, yy)[1]), metin, font=font, fill=renk)
    return im


# ── zaman çizelgesi ──────────────────────────────────────────────────────────
def main():
    pdf, satirlar, olculen = gercek_calistir()
    islem = max(olculen, 0.6)   # asla ölçülenden KISA gösterme
    print(f"ölçülen işlem süresi: {olculen:.2f} sn → animasyonda {islem:.2f} sn")

    zemin = Image.new("RGBA", s(W, H), MASA + (255,))
    zemin.alpha_composite(pdf_penceresi(pdf), s(20, 20))
    tablo = tablo_penceresi(satirlar)
    son = kapanis()
    dosya, dosya_secili, hayalet = dosya_simgesi(), dosya_simgesi(secili=True), dosya_simgesi(etiket=False)
    hayalet.putalpha(hayalet.getchannel("A").point(lambda a: int(a * 0.72)))
    uyg, uyg_vurgu = uygulama_simgesi(), uygulama_simgesi(vurgu=True)

    DOSYA_M, UYG_M = (650, 360), (650, 175)
    T_BIRAK = 2.5
    T_TABLO = T_BIRAK + islem
    T_SON = 6.4

    kareler = Path(tempfile.mkdtemp())
    toplam = int(SURE * FPS)
    for k in range(toplam):
        t = k / FPS
        kare = zemin.copy()
        if t < T_SON + 0.2:
            birakildi = t >= T_BIRAK
            secili = 1.0 <= t < T_BIRAK
            kare.alpha_composite(dosya_secili if secili else dosya, s(DOSYA_M[0] - 60, DOSYA_M[1] - 36))
            # uygulama simgesi: üzerine gelinince vurgu, işlem sırasında zıplama
            if T_BIRAK <= t < T_TABLO:
                faz = (t - T_BIRAK) / islem
                olcek = 1 + 0.07 * abs(math.sin(faz * math.pi * 2))
                kare.alpha_composite(uygulama_simgesi(olcek=olcek), s(UYG_M[0] - 65, UYG_M[1] - 55))
            else:
                ust = 2.15 <= t < T_BIRAK
                kare.alpha_composite(uyg_vurgu if ust else uyg, s(UYG_M[0] - 65, UYG_M[1] - 55))
            # imleç yolu
            if t < 1.0:
                a = yumusak(t / 1.0)
                cx, cy = 560 + (DOSYA_M[0] - 560) * a, 450 + (DOSYA_M[1] - 450) * a
            elif t < 1.3:
                cx, cy = DOSYA_M
            elif t < T_BIRAK:
                a = yumusak((t - 1.3) / (T_BIRAK - 1.3))
                cx = DOSYA_M[0] + 26 * math.sin(a * math.pi)
                cy = DOSYA_M[1] + (UYG_M[1] - DOSYA_M[1]) * a
                kare.alpha_composite(hayalet, s(cx - 60, cy - 36))
            elif t < T_TABLO + 1.0:
                cx, cy = UYG_M
            else:
                a = yumusak(min(1.0, (t - T_TABLO - 1.0) / 0.9))
                hedef = (70 + 590 + 60, 44 + 27 + 20 + 24 + 12)   # işaretli "Kontrol" hücresi
                cx, cy = UYG_M[0] + (hedef[0] - UYG_M[0]) * a, UYG_M[1] + (hedef[1] - UYG_M[1]) * a
            if t >= T_TABLO:
                g = min(1.0, (t - T_TABLO) / 0.25)
                olc = 0.96 + 0.04 * yumusak(g)
                tw, th = int(tablo.width * olc), int(tablo.height * olc)
                parca = tablo.resize((tw, th), Image.LANCZOS)
                parca.putalpha(parca.getchannel("A").point(lambda a, g=g: int(a * g)))
                kare.alpha_composite(parca, (s(70)[0] + (tablo.width - tw) // 2, s(0, 44)[1] + (tablo.height - th) // 2))
            imlec(ImageDraw.Draw(kare), cx, cy, basili=(1.0 <= t < T_BIRAK))
        if t >= T_SON:
            g = min(1.0, (t - T_SON) / 0.2)
            kare = Image.blend(kare, son, g)
        kare.convert("RGB").resize((W, H), Image.LANCZOS).save(kareler / f"g{k:04d}.png")
        kare.convert("RGB").resize((1280, 768), Image.LANCZOS).save(kareler / f"m{k:04d}.png")

    cikti = KOK / "docs"
    palet = kareler / "palet.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(kareler / "g%04d.png"),
                    "-vf", "palettegen=max_colors=128:stats_mode=diff", str(palet)], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(kareler / "g%04d.png"),
                    "-i", str(palet), "-lavfi", "paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle",
                    "-loop", "0", str(cikti / "demo.gif")], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(kareler / "m%04d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "24", "-movflags", "+faststart",
                    str(cikti / "demo.mp4")], check=True)
    shutil.copy(kareler / "g0028.png", cikti / "_kare_suruklenirken.png")
    shutil.copy(kareler / "g0035.png", cikti / "_kare_uzerinde.png")
    shutil.copy(kareler / f"g{int((T_TABLO + 1.6) * FPS):04d}.png", cikti / "_kare_tablo.png")
    shutil.copy(kareler / "g0115.png", cikti / "_kare_kapanis.png")
    shutil.rmtree(kareler)
    for ad in ("demo.gif", "demo.mp4"):
        print(f"✓ docs/{ad}  {(cikti / ad).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
