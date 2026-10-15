#!/bin/bash

# Copies additions and settings into the Firefox source directory.
# Must be run from within the source directory.
# Matches Cloakfox's copy-additions.sh flow.
#
# Usage: $0 <version> <release> [repo_dir]
# repo_dir defaults to .. (assumes source dir is inside the repo)

if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <version> <release> [repo_dir]"
    exit 1
fi

version="$1"
release="$2"
REPO="${3:-..}"

run() {
    echo "$ $1"
    eval "$1"
    if [ $? -ne 0 ]; then
        echo "Command failed: $1"
        exit 1
    fi
}

# Copy settings into lw/ directory
run 'mkdir -p lw'
python3 "$REPO/scripts/stage_ublock.py" --output-dir lw/ublock-origin || exit 1
python3 "$REPO/scripts/stage_container_addons.py" --output-dir lw/container-addons || exit 1
run "cp -v $REPO/settings/cloakfox.cfg lw/cloakfox.cfg"
[ -f "$REPO/settings/policies.json" ] && run "cp -v $REPO/settings/policies.json lw/"
[ -f "$REPO/settings/local-settings.js" ] && run "cp -v $REPO/settings/local-settings.js lw/"
[ -f "$REPO/settings/chrome.css" ] && run "cp -v $REPO/settings/chrome.css lw/"
[ -f "$REPO/settings/properties.json" ] && run "cp -v $REPO/settings/properties.json lw/"
run 'touch lw/moz.build'

# Extension is copied as part of additions/ (browser/extensions/cloakfox-shield/)

# Copy librewolf pack_vs.py (referenced by build system)
run "cp -v '$REPO/patches/librewolf/pack_vs.py' build/vs/" || true

# Copy ALL new files/folders from additions to source
run "cp -r '$REPO/additions/'* ."

# Verify pinned font bytes and refresh our owned install list, including new
# assets when this script is repeated against an existing checkout.
if ls "$REPO/bundle/fonts/macos/"*.ttf >/dev/null 2>&1; then
    run "python3 '$REPO/scripts/audit-font-pack.py' --check"
    run "python3 '$REPO/scripts/stage-font-resources.py' --bundle '$REPO/bundle/fonts' --target browser/fonts"
fi

# Stage the isolated renderer only after every pinned resource hash verifies.
if [ -d "$REPO/bundle/canonical-gpu" ]; then
    run "python3 '$REPO/scripts/stage-canonical-gpu.py' --bundle '$REPO/bundle/canonical-gpu' --target browser/canonical-gpu"
fi

# Override the firefox version
for file in "browser/config/version.txt" "browser/config/version_display.txt"; do
    echo "${version}-${release}" > "$file"
done

echo "Additions and settings copied successfully."
