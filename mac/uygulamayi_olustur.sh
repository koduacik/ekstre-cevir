#!/bin/bash
# "Ekstre Çevir.app" uygulamasını AppleScript kaynağından yeniden oluşturur.
set -euo pipefail
KLASOR="$(cd "$(dirname "$0")/.." && pwd)"
UYGULAMA="$KLASOR/Ekstre Çevir.app"
PLIST="$UYGULAMA/Contents/Info.plist"

rm -rf "$UYGULAMA"
osacompile -o "$UYGULAMA" "$KLASOR/mac/Ekstre Çevir.applescript"

# Yalnızca PDF bırakılabilsin
/usr/libexec/PlistBuddy -c "Delete :CFBundleDocumentTypes" "$PLIST" 2>/dev/null || true
/usr/libexec/PlistBuddy \
    -c "Add :CFBundleDocumentTypes array" \
    -c "Add :CFBundleDocumentTypes:0 dict" \
    -c "Add :CFBundleDocumentTypes:0:CFBundleTypeName string PDF" \
    -c "Add :CFBundleDocumentTypes:0:CFBundleTypeRole string Viewer" \
    -c "Add :CFBundleDocumentTypes:0:LSItemContentTypes array" \
    -c "Add :CFBundleDocumentTypes:0:LSItemContentTypes:0 string com.adobe.pdf" \
    "$PLIST"
/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier com.example.ekstrecevir" "$PLIST" 2>/dev/null ||
    /usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string com.example.ekstrecevir" "$PLIST"

# Info.plist değişince imza bozulur; yerel (ad-hoc) imzayla yenile
codesign --force --deep --sign - "$UYGULAMA"
echo "Oluşturuldu: $UYGULAMA"
