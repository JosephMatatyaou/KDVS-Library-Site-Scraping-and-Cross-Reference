#!/usr/bin/env bash
# Build script for Intel/x86_64 macOS apps (runs under Rosetta emulation)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -x "$ROOT_DIR/.venv-intel/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv-intel/bin/python"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

cd "$ROOT_DIR"

# Run under x86_64 architecture
arch -x86_64 "$PYTHON_BIN" -m PyInstaller --clean --noconfirm TheCharter3000-intel.spec

# Remove quarantine and code signing attributes
if command -v xattr >/dev/null 2>&1; then
  xattr -cr dist/TheCharter3000.app || true
fi

# Ad-hoc code sign the app for macOS compatibility
if command -v codesign >/dev/null 2>&1; then
  codesign --force --deep --sign - dist/TheCharter3000.app 2>/dev/null || true
fi

rm -f dist/TheCharter3000-macOS-intel.zip
ditto -c -k --sequesterRsrc --keepParent dist/TheCharter3000.app dist/TheCharter3000-macOS-intel.zip

printf 'Created %s\n' "$ROOT_DIR/dist/TheCharter3000-macOS-intel.zip"
