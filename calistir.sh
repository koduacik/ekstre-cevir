#!/bin/bash
# Ekstre Çevir — macOS başlatıcısı.
# İlk çalıştırmada bu klasöre .venv kurar ve bağımlılıkları yükler, sonra
# ekstre_cevir.py'yi aynı argümanlarla çalıştırır (ör. --yol belge.pdf).
# Kurulum çıktısı stdout'u kirletmesin diye .kurulum.log dosyasına yazılır.
set -u

KLASOR="$(cd "$(dirname "$0")" && pwd)"
VENV="$KLASOR/.venv"
LOG="$KLASOR/.kurulum.log"
DAMGA="$VENV/.kurulum_tamam"
export PYTHONIOENCODING=utf-8

hata() { printf '%s\n' "$*" >&2; exit 1; }

kurulu_mu() {
    [ -x "$VENV/bin/python" ] &&
    "$VENV/bin/python" -c "import pdfplumber, openpyxl" >/dev/null 2>&1 &&
    cmp -s "$KLASOR/requirements.txt" "$DAMGA"
}

uygun_python() {
    "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1
}

python_bul() {
    # Uygulamadan çalışınca PATH çok kısadır; bilinen yerlere tek tek bakılır.
    local aday
    for aday in \
        /opt/homebrew/bin/python3 \
        /usr/local/bin/python3 \
        /Library/Frameworks/Python.framework/Versions/3.*/bin/python3 \
        "$HOME/.pyenv/shims/python3" \
        "$(command -v python3 2>/dev/null)"; do
        [ -x "$aday" ] || continue
        [ "$aday" = /usr/bin/python3 ] && continue
        uygun_python "$aday" && { echo "$aday"; return 0; }
    done
    # /usr/bin/python3 yalnızca Komut Satırı Araçları kuruluysa gerçek Python'dur;
    # değilse çağırmak kurulum penceresi açar.
    if xcode-select -p >/dev/null 2>&1 && uygun_python /usr/bin/python3; then
        echo /usr/bin/python3; return 0
    fi
    return 1
}

if ! kurulu_mu; then
    PY="$(python_bul)" || hata "Python 3.9 veya üstü bulunamadı.
python.org/downloads adresinden Python'u kurup tekrar deneyin."
    {
        echo "== $(date) — kurulum, $PY"
        rm -rf "$VENV"
        "$PY" -m venv "$VENV" &&
        "$VENV/bin/python" -m pip install --disable-pip-version-check -r "$KLASOR/requirements.txt"
    } >>"$LOG" 2>&1 || hata "Gerekli bileşenler kurulamadı. İnternet bağlantınızı kontrol edip tekrar deneyin.
Ayrıntılar: $LOG"
    cp "$KLASOR/requirements.txt" "$DAMGA"
fi

exec "$VENV/bin/python" "$KLASOR/ekstre_cevir.py" "$@"
