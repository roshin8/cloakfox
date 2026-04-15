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
run "cp -v $REPO/settings/cloakfox.cfg lw/cloakfox.cfg"
[ -f "$REPO/settings/policies.json" ] && run "cp -v $REPO/settings/policies.json lw/"
[ -f "$REPO/settings/local-settings.js" ] && run "cp -v $REPO/settings/local-settings.js lw/"
[ -f "$REPO/settings/chrome.css" ] && run "cp -v $REPO/settings/chrome.css lw/"
[ -f "$REPO/settings/properties.json" ] && run "cp -v $REPO/settings/properties.json lw/"
run 'touch lw/moz.build'

# Copy bundled extension XPI if it exists
# Goes to browser/extensions/ (app scope) — discovered via enabledScopes
if [ -f "$REPO/cloakfox-shield.xpi" ]; then
    run "mkdir -p browser/extensions"
    run "cp -v $REPO/cloakfox-shield.xpi browser/extensions/cloakfox-shield@cloakfox.xpi"
fi

# Copy librewolf pack_vs.py (referenced by build system)
run "cp -v '$REPO/patches/librewolf/pack_vs.py' build/vs/" || true

# Copy ALL new files/folders from additions to source
run "cp -r '$REPO/additions/'* ."

# Override the firefox version
for file in "browser/config/version.txt" "browser/config/version_display.txt"; do
    echo "${version}-${release}" > "$file"
done

echo "Additions and settings copied successfully."
