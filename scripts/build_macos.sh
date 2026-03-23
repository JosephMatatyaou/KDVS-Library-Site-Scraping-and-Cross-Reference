#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/build-arm64"
DIST_DIR="$ROOT_DIR/dist-arm64"
ZIP_PATH="$ROOT_DIR/dist/TheCharter3000-macOS-arm64.zip"
PYINSTALLER_CONFIG_DIR="${PYINSTALLER_CONFIG_DIR:-/tmp/pyinstaller-arm64}"

if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

cd "$ROOT_DIR"

mkdir -p "$ROOT_DIR/dist"
mkdir -p "$PYINSTALLER_CONFIG_DIR"

PYINSTALLER_CONFIG_DIR="$PYINSTALLER_CONFIG_DIR" "$PYTHON_BIN" -m PyInstaller \
  --clean \
  --noconfirm \
  --workpath "$BUILD_DIR" \
  --distpath "$DIST_DIR" \
  TheCharter3000.spec

# Remove quarantine and code signing attributes
if command -v xattr >/dev/null 2>&1; then
  xattr -cr "$DIST_DIR/TheCharter3000.app" || true
fi

# Ad-hoc code sign the app for macOS compatibility
if command -v codesign >/dev/null 2>&1; then
  codesign --force --deep --sign - "$DIST_DIR/TheCharter3000.app" 2>/dev/null || true
fi

rm -f "$ZIP_PATH"
ditto -c -k --sequesterRsrc --keepParent "$DIST_DIR/TheCharter3000.app" "$ZIP_PATH"

printf 'Created %s\n' "$ZIP_PATH"
