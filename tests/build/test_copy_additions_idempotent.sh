#!/bin/bash
# Regression test for the non-idempotent FINAL_TARGET_FILES.fonts append in
# scripts/copy-additions.sh. The standard flow runs the script TWICE (make setup
# then make dir re-runs it), so a second run must NOT duplicate the font install
# block — a duplicate makes mozbuild fail with "Item already in manifest".
#
# Exit 0 = idempotent (one block after two runs). Exit 1 = regressed.
set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$REPO_ROOT/scripts/copy-additions.sh"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

# Minimal fake repo the script copies from.
repo="$work/repo"
mkdir -p "$repo/settings" "$repo/additions/placeholder" \
         "$repo/patches/librewolf" "$repo/bundle/fonts/macos"
echo '// cfg' > "$repo/settings/cloakfox.cfg"
echo '# pack_vs' > "$repo/patches/librewolf/pack_vs.py"
: > "$repo/bundle/fonts/macos/Arial.ttf"
: > "$repo/bundle/fonts/macos/Verdana.ttf"

# Minimal fake extracted firefox source dir (script runs from inside it).
src="$work/firefox-src"
mkdir -p "$src/build/vs" "$src/browser/fonts" "$src/browser/config"
printf '# base moz.build\n' > "$src/browser/fonts/moz.build"

run_once() {
    ( cd "$src" && bash "$SCRIPT" 146.0.1 1 "$repo" ) >/dev/null 2>&1
}

run_once
run_once

count=$(grep -c "Cloakfox: bundled open-substitute font pack" \
        "$src/browser/fonts/moz.build")
dupes=$(grep -c '"Arial.ttf",' "$src/browser/fonts/moz.build")

if [[ "$count" -eq 1 && "$dupes" -eq 1 ]]; then
    echo "PASS — font install block present exactly once after two runs"
    exit 0
fi
echo "FAIL — block appears $count time(s), Arial.ttf entry $dupes time(s) (expected 1/1)"
echo "--- moz.build ---"
cat "$src/browser/fonts/moz.build"
exit 1
