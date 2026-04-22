#!/usr/bin/env bash
# End-to-end test for the cpp-first-exploration POC.
#
# Mounts the CI-produced DMG, extracts Cloakfox.app, strips macOS quarantine,
# launches headless with a fresh profile, and asserts:
#   - Math.PI / Math.E are perturbed (CloakfoxMath actor fired)
#   - about:cloakfox registers and renders the settings page
#
# Usage:
#   ./scripts/test-cpp-first-poc.sh [path/to/dmg]
#
# If no DMG arg is passed, uses:
#   /tmp/cfx-artifact/cloakfox-macos-arm64/Cloakfox-macos-arm64.dmg

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DMG="${1:-/tmp/cfx-artifact/cloakfox-macos-arm64/Cloakfox-macos-arm64.dmg}"

if [ ! -f "$DMG" ]; then
    echo "ERROR: DMG not found at $DMG" >&2
    echo "Download with:  gh run download <run-id> --dir /tmp/cfx-artifact" >&2
    exit 2
fi

# Minimal virtualenv for selenium — avoids polluting system Python and
# keeps the script self-contained.
VENV="$REPO_DIR/tests/.cpp-first-venv"
if [ ! -d "$VENV" ]; then
    echo "[setup] creating venv at $VENV"
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install --quiet --upgrade pip
    "$VENV/bin/pip" install --quiet selenium
fi

# geckodriver: selenium's Firefox driver. Prefer a Homebrew-installed one
# if present; otherwise fall back to whatever selenium auto-downloads.
if ! command -v geckodriver >/dev/null 2>&1; then
    echo "[setup] geckodriver missing; trying to install via Homebrew..."
    if command -v brew >/dev/null 2>&1; then
        brew install geckodriver >/dev/null
    else
        echo "ERROR: geckodriver not found and Homebrew is not installed." >&2
        echo "Install geckodriver manually, or install Homebrew first." >&2
        exit 2
    fi
fi

echo "[run] CLOAKFOX_DMG=$DMG python $REPO_DIR/tests/fingerprint/probe_cpp_first.py"
echo
CLOAKFOX_DMG="$DMG" "$VENV/bin/python" "$REPO_DIR/tests/fingerprint/probe_cpp_first.py"
