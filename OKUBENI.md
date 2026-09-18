# Ekstre Çevir

PDF banka ekstresini Excel'e çevirir. Belge ekstre değilse içindeki tabloları Excel'e aktarır.
Dosyalar bilgisayardan çıkmaz; program internete yalnızca ilk kurulumda, bileşenleri indirmek için bağlanır.

## Mac'te kullanım

1. Bu klasörü kalıcı bir yere koyun (ör. Belgeler). **Ekstre Çevir** uygulaması bu klasörün içinde kalmalı.
   Masaüstüne koymak isterseniz: uygulamaya sağ tıklayın → *Kısayol Oluştur*, çıkan kısayolu masaüstüne sürükleyin.
2. PDF'i **Ekstre Çevir** simgesinin üstüne bırakın. Excel kendiliğinden açılır.
   Simgeye çift tıklarsanız dosya seçme penceresi açılır.
3. Excel dosyası PDF'in yanına kaydedilir:
   - banka ekstresi → `Belge Adı_ekstre.xlsx`
   - ekstre değil ama tablo var → `Belge Adı_tablo.xlsx` (her tablo ayrı sayfada)

İlk kullanımda gerekli bileşenler kurulur (internet gerekir, 1-2 dakika). Bilgisayarda Python 3.9 veya
üstü olmalı; yoksa program uyarır, python.org/downloads adresinden kurulabilir.
macOS bir klasöre erişim izni sorarsa *İzin Ver* deyin.

## Windows'ta kullanım

PDF'i **Ekstre Cevir.bat** dosyasının üstüne bırakın. Python kurulu olmalı (python.org; kurulumda
*Add python.exe to PATH* kutusunu işaretleyin).

## Kontrol kolonu

Her tutar, bir önceki bakiyeyle aradaki farka göre doğrulanır. Tutmayan satır atlanmaz, sarıyla işaretlenir:

| Kontrol | Anlamı |
|---|---|
| *(boş)* | Tutar, bakiye farkıyla doğrulandı. |
| Bakiye tutmuyor: … | Tutar bakiye farkına uymuyor. Ekstreyle karşılaştırın. |
| İlk hareket: önceki bakiye yok, tutar doğrulanamadı | Ekstrede devreden bakiye yok; ilk satırın tutarı kontrol edilemedi. |
| İlk hareket: … işaret türetilemedi | Borç/alacak ayrı kolonlu ekstrede ilk satırın borç mu alacak mı olduğu anlaşılamadı; tutar işaretsiz yazıldı. |

Borç ve alacağı ayrı kolonda veren ekstrelerde işaret bakiye farkından bulunur: borç eksi, alacak artı yazılır.
En yeni hareketi en üstte gösteren ekstreler de tanınır.

## Excel ne zaman oluşmaz?

Program boş Excel üretmez, nedenini söyler:
- belgede ne banka ekstresi ne tablo varsa (ör. yalnızca yazıdan oluşan belge),
- PDF taranmış ya da fotoğraftan oluşturulmuşsa (metni seçilemiyorsa),
- dosya parolalı ya da bozuksa.

Satırları tarihle başlayan ama bakiyeyle doğrulanamayan belgeler (ör. günlük satış raporu) ekstre sayılmaz,
tablo olarak aktarılır.

## Bilinen sınırlar

- Taranmış PDF'lerde yazı tanıma (OCR) yok.
- Kenarlıksız tablolarda kolonlar, sağa hizalı sayılardan bulunur; hiç sayı kolonu olmayan kenarlıksız
  tablolar algılanmaz. Kenarlıksız tabloda hücre içinde alt satıra geçen metin ayrı satır olarak gelir.
- Windows başlatıcısı Windows'ta denenmedi (Mac'te uçtan uca denendi).

## Geliştirici notları

```bash
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python -m unittest discover -s tests -v
```

- `ekstre_cevir.py belge.pdf` sonucu anlatır; `ekstre_cevir.py --yol belge.pdf` yalnızca üretilen dosyanın yolunu yazar.
  Hata olursa mesaj stderr'e gider ve çıkış kodu 1 olur.
- Testler her çalışmada sahte ekstreleri ve tablo belgelerini reportlab ile yeniden üretir, programı
  komut satırından çalıştırır ve Excel çıktısını beklenen CSV'lerle hücre hücre karşılaştırır.
  Örnek belgeleri görmek için: `.venv/bin/python tests/ornek_uret.py` (→ `tests/ornekler/`).
- Uygulamayı AppleScript kaynağından yeniden oluşturmak için: `mac/uygulamayi_olustur.sh`
