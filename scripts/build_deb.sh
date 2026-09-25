#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
ARCH=$(dpkg --print-architecture)
STAGE=build/deb
OUT="tex-capture_${VERSION}-1_${ARCH}.deb"

rm -rf "$STAGE"
mkdir -p "$STAGE/DEBIAN" "$STAGE/opt/tex/lib" "$STAGE/usr/bin" \
         "$STAGE/usr/share/applications" "$STAGE/usr/share/icons/hicolor/scalable/apps"

if python3 -m pip --version >/dev/null 2>&1; then
    PIP="python3 -m pip"
else
    PIP=".venv/bin/pip"
fi

echo ">> installing application into staging tree"
$PIP install --quiet --no-compile --no-deps --target "$STAGE/opt/tex/lib" .
$PIP install --quiet --no-compile --upgrade --target "$STAGE/opt/tex/lib" \
    PySide6-Essentials mss pytesseract dbus-next python-xlib tomli-w
find "$STAGE/opt/tex/lib" -depth -name "__pycache__" -type d -exec rm -rf {} +

echo ">> wrapper, desktop entry, icon"
cat > "$STAGE/usr/bin/tex" <<'EOF'
#!/bin/sh
PYTHONPATH=/opt/tex/lib${PYTHONPATH:+:$PYTHONPATH} exec python3 -m tex "$@"
EOF
chmod 755 "$STAGE/usr/bin/tex"

install -m 644 data/tex.desktop "$STAGE/usr/share/applications/tex.desktop"
install -m 644 data/icons/hicolor/scalable/apps/tex.svg \
    "$STAGE/usr/share/icons/hicolor/scalable/apps/tex.svg"

cat > "$STAGE/DEBIAN/control" <<EOF
Package: tex-capture
Version: ${VERSION}-1
Section: graphics
Priority: optional
Architecture: ${ARCH}
Depends: python3 (>= 3.10), python3-pil, python3-requests
Recommends: tesseract-ocr, xdg-desktop-portal
Suggests: python3-keyring, grim, slurp
Maintainer: SlyHammad18
Homepage: https://github.com/SlyHammad18/tex
Description: Screenshot capture with AI text extraction
 Capture a region, window, or the full screen and extract text offline
 via Tesseract or online via Gemini, Groq, Cerebras, and OpenRouter
 vision models, including parallel multi-model compare mode.
EOF

cat > "$STAGE/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -qf /usr/share/icons/hicolor || true
fi
EOF
chmod 755 "$STAGE/DEBIAN/postinst"

echo ">> building $OUT"
dpkg-deb --root-owner-group --build "$STAGE" "$OUT"
echo ">> done: $OUT ($(du -h "$OUT" | cut -f1))"
