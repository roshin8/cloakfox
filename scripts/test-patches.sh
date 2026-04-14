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

# Apply all patches in sorted order
echo ""
echo "=== Applying patches ==="
FAILED=0
APPLIED=0
for p in $(find "$REPO_DIR/patches" -name '*.patch' | sort); do
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
