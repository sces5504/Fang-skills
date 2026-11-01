#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -c 'import platform; assert platform.system() == "Darwin" and platform.machine() == "arm64", "請使用 Apple Silicon 原生 Python"'
"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m pytest
.venv/bin/python -m PyInstaller --noconfirm --clean NTEOwnerMac.spec
./dist/NTEOwnerMac.app/Contents/MacOS/NTEOwnerMac --self-test
codesign --verify --deep --strict dist/NTEOwnerMac.app
ditto -c -k --sequesterRsrc --keepParent dist/NTEOwnerMac.app dist/NTEOwnerMac-arm64.zip
