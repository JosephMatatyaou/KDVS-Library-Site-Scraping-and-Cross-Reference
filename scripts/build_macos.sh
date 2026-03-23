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

if command -v xattr >/dev/null 2>&1; then
  xattr -cr dist/TheCharter3000.app || true
fi

rm -f dist/TheCharter3000-macOS.zip
ditto -c -k --sequesterRsrc --keepParent dist/TheCharter3000.app dist/TheCharter3000-macOS.zip

printf 'Created %s\n' "$ROOT_DIR/dist/TheCharter3000-macOS.zip"
