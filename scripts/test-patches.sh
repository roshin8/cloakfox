#!/usr/bin/env bash
set -euo pipefail

# Tests all patches against a fresh Firefox source extraction.
# Downloads the tarball if not present, extracts, copies additions,
# then applies all patches in sorted order (same as Cloakfox's patch.py).
#
# Usage: scripts/test-patches.sh

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$REPO_DIR/upstream.sh"

FF_TARBALL="$REPO_DIR/firefox-${version}.source.tar.xz"
TEST_DIR="/tmp/cloakfox-patch-test"

echo "Testing patches against Firefox ${version}..."

# Download if needed
if [ ! -f "$FF_TARBALL" ]; then
    echo "Downloading Firefox ${version} source..."
    "$REPO_DIR/scripts/fetch-firefox.sh" "$version"
fi

# Clean and extract
rm -rf "$TEST_DIR"
mkdir -p "$TEST_DIR"
echo "Extracting..."
tar -xJf "$FF_TARBALL" -C "$TEST_DIR" --strip-components=1

# Copy additions (like Cloakfox's setup-minimal)
echo "Copying additions..."
cd "$TEST_DIR"
bash "$REPO_DIR/scripts/copy-additions.sh" "$version" "$release" "$REPO_DIR" >/dev/null 2>&1

# Apply all patches — respect order.txt first, then anything unlisted (alphabetical).
echo ""
echo "=== Applying patches ==="
FAILED=0
APPLIED=0

ORDERED=()
if [ -f "$REPO_DIR/patches/order.txt" ]; then
    while IFS= read -r line; do
        line="${line%%#*}"
        line="${line// /}"
        line="${line//$'\t'/}"
        [ -z "$line" ] && continue
        if [ -f "$REPO_DIR/patches/$line" ]; then
            ORDERED+=("$REPO_DIR/patches/$line")
        fi
    done < "$REPO_DIR/patches/order.txt"
fi
# Append any unlisted patches (alphabetical)
for p in $(find "$REPO_DIR/patches" -name '*.patch' | sort); do
    name=$(basename "$p")
    listed=0
    for existing in "${ORDERED[@]}"; do
        [ "$(basename "$existing")" = "$name" ] && listed=1 && break
    done
    [ $listed -eq 0 ] && ORDERED+=("$p")
done

for p in "${ORDERED[@]}"; do
    name=$(basename "$p")
    echo -n "  $name ... "
    result=$(patch -p1 --force -i "$p" < /dev/null 2>&1)
    if echo "$result" | grep -q "malformed\|FAILED\|ignored"; then
        echo "FAILED"
        echo "$result" | grep -E "malformed|FAILED|Hunk" | sed 's/^/    /'
        FAILED=$((FAILED + 1))
    else
        echo "OK"
        APPLIED=$((APPLIED + 1))
    fi
done

# Clean up
rm -rf "$TEST_DIR"

echo ""
echo "================================"
echo "Applied: $APPLIED"
echo "Failed:  $FAILED"
if [ $FAILED -eq 0 ]; then
    echo "ALL PATCHES OK"
    exit 0
else
    echo "SOME PATCHES FAILED"
    exit 1
fi
