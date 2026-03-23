#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

cd "$ROOT_DIR"

"$PYTHON_BIN" -m PyInstaller --clean --noconfirm TheCharter3000.spec

# Remove quarantine and code signing attributes
if command -v xattr >/dev/null 2>&1; then
  xattr -cr dist/TheCharter3000.app || true
fi

# Ad-hoc code sign the app for macOS compatibility
if command -v codesign >/dev/null 2>&1; then
  codesign --force --deep --sign - dist/TheCharter3000.app 2>/dev/null || true
fi

rm -f dist/TheCharter3000-macOS-arm64.zip
ditto -c -k --sequesterRsrc --keepParent dist/TheCharter3000.app dist/TheCharter3000-macOS-arm64.zip

printf 'Created %s\n' "$ROOT_DIR/dist/TheCharter3000-macOS-arm64.zip"
