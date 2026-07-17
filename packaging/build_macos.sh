#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

uv run pyinstaller packaging/gestionale.spec \
    --distpath dist/macos \
    --workpath build/macos \
    --noconfirm

echo "Build completata: dist/macos/GestionaleLogistica.app"
