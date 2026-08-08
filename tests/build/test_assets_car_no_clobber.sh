#!/bin/bash
# Regression test for generate-assets-car.sh (finding #11): on a machine without
# full Xcode (actool absent), the script must NOT overwrite an already-committed
# real Assets.car with Firefox's placeholder. Runs a COPY of the script inside a
# throwaway repo so the real tree is never touched.
set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC_SCRIPT="$REPO_ROOT/scripts/generate-assets-car.sh"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

# Fake repo layout the copied script will resolve REPO_DIR to.
mkdir -p "$work/repo/scripts"
cp "$SRC_SCRIPT" "$work/repo/scripts/generate-assets-car.sh"

brand="$work/repo/additions/browser/branding/cloakfox"
mkdir -p "$brand"
REAL="CLOAKFOX-REAL-ICON-BYTES"
printf '%s' "$REAL" > "$brand/Assets.car"        # committed real icon

# A placeholder the script could fall back to.
official="$work/repo/firefox-src/browser/branding/official"
mkdir -p "$official"
printf '%s' "FIREFOX-PLACEHOLDER-BYTES" > "$official/Assets.car"

# Force the no-actool path: a fake `xcrun` that always fails, and a PATH with no
# actool. (On Command-Line-Tools-only machines this is the real situation.)
stub="$work/bin"
mkdir -p "$stub"
cat > "$stub/xcrun" <<'EOF'
#!/bin/bash
exit 1
EOF
chmod +x "$stub/xcrun"

PATH="$stub:/usr/bin:/bin" bash "$work/repo/scripts/generate-assets-car.sh" \
    >/dev/null 2>&1

got="$(cat "$brand/Assets.car")"
if [[ "$got" == "$REAL" ]]; then
    echo "PASS — committed Assets.car preserved (not overwritten by placeholder)"
    exit 0
fi
echo "FAIL — committed Assets.car was clobbered; now: ${got}"
exit 1
