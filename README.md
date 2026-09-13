# Ekstre Çevir

PDF banka ekstresini Excel'e çeviren tek dosyalık program. Kurulum yok, ücretsiz, dosyanız bilgisayarınızdan çıkmıyor.

> Bu araç **Bunun Programı Var** kanalının 1. bölümünde sıfırdan yazıldı.
> Video: <video-linki>  ·  Kanal: https://youtube.com/@programivar

## İndir

En güncel sürüm: [Releases](../../releases/latest)

## Ne yapar

- PDF ekstreden `tarih / açıklama / tutar / bakiye` kolonlarını çıkarır, `.xlsx` verir
- Türk sayı biçimini doğru okur (1.234,56 → 1234.56)
- Çok satıra bölünmüş açıklamaları tek hücrede birleştirir
- Okunamayan satırı atlamaz; `kontrol` kolonunda işaretler

## Ne yapmaz

- Taranmış (fotoğraf) PDF okumaz — metin katmanı gerekir
- Kredi kartı ekstresi farklı düzendedir, ayrı profil ister
- Her bankanın düzeni farklı; 3 banka profiliyle geliyor, yenisini eklemek ~10 satır

## Gizlilik

Bu program hiçbir veriyi internete göndermez. Dosyalarınız kendi bilgisayarınızda kalır;
program çalışırken internet bağlantısı gerekmez.

## Destek

Destek sözü vermiyorum. Kod açık — hata bulursan issue aç, düzeltirsen pull request gönder,
kendi ihtiyacına göre değiştirmek istersen çekinme.

## Lisans

MIT — bkz. [LICENSE](LICENSE)
