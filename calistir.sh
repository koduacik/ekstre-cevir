#!/bin/bash
# Ekstre Çevir çalıştırıcı (ekstre ya da tablolu PDF) — "Ekstre Çevir.app" bunu çağırır, elle de kullanılabilir:
#   ./calistir.sh ekstre.pdf
# İlk çalıştırmada klasörün içine .venv kurar (bir kez, internet gerekir).
# SON SATIR her zaman üretilen .xlsx dosyasının yoludur.
set -e
KLASOR="$(cd "$(dirname "$0")" && pwd)"
PDF="$1"
[ -f "$PDF" ] || { echo "PDF bulunamadı: $PDF" >&2; exit 1; }

if [ ! -x "$KLASOR/.venv/bin/python" ]; then
  for p in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
    [ -x "$p" ] && PY="$p" && break
  done
  [ -n "${PY:-}" ] || { echo "Python 3 bulunamadı" >&2; exit 1; }
  "$PY" -m venv "$KLASOR/.venv" >&2
  "$KLASOR/.venv/bin/python" -m pip install -q --disable-pip-version-check -r "$KLASOR/requirements.txt" >&2
fi

# --yol: insan mesajları stderr'e, üretilen dosyanın yolu stdout'a (ekstre ya da tablo)
XLSX="$("$KLASOR/.venv/bin/python" "$KLASOR/ekstre_cevir.py" --yol "$PDF")"
[ -n "$XLSX" ] && [ -f "$XLSX" ] || { echo "Excel dosyası üretilemedi" >&2; exit 1; }
echo "$XLSX"
