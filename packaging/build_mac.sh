#!/usr/bin/env bash
# Build dist/GraphMTG.app and dist/GraphMTG-mac.zip (macOS, Apple Silicon).
#
#   bash packaging/build_mac.sh        # uses .venv if present, else python3
#
# Steps: build the web UI (npm ci + npm run build), install PyInstaller, run the spec, zip the app.
# The app is ad-hoc signed by PyInstaller (required on Apple Silicon) but not notarized (D-022).
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

if [ -x .venv/bin/python ]; then python=.venv/bin/python; else python=python3; fi

echo "==> Building web UI"
(cd web && npm ci --no-fund --no-audit && npm run build)

echo "==> Installing build dependencies"
"$python" -m pip install --quiet "pyinstaller==6.22.3" "rumps>=0.4" "httpx>=0.27" "fastapi>=0.115" "uvicorn>=0.30"

echo "==> Running PyInstaller"
"$python" -m PyInstaller --noconfirm --clean --distpath dist --workpath build/pyinstaller packaging/GraphMTG.spec

echo "==> Zipping"
rm -f dist/GraphMTG-mac.zip
# ditto keeps the bundle's symlinks and signature intact (plain zip can break them).
ditto -c -k --sequesterRsrc --keepParent dist/GraphMTG.app dist/GraphMTG-mac.zip

echo "==> Built $root/dist/GraphMTG.app ($(du -sh dist/GraphMTG.app | cut -f1)), zipped to dist/GraphMTG-mac.zip ($(du -h dist/GraphMTG-mac.zip | cut -f1))"
