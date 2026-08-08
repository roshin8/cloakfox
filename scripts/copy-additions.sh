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

# Extension is copied as part of additions/ (browser/extensions/cloakfox-shield/)

# Copy librewolf pack_vs.py (referenced by build system)
run "cp -v '$REPO/patches/librewolf/pack_vs.py' build/vs/" || true

# Copy ALL new files/folders from additions to source
run "cp -r '$REPO/additions/'* ."

# Cloakfox: stage the bundled open-substitute font pack into browser/fonts and
# append a FINAL_TARGET_FILES.fonts install rule, so the pack is installed to
# dist/bin/fonts and packaged into Contents/Resources/fonts (activated at
# runtime by MOZ_BUNDLED_FONTS / ActivateBundledFonts). The Mac manifest entry
# is added by patches/font-bundle-packaging.patch.
if ls "$REPO/bundle/fonts/macos/"*.ttf >/dev/null 2>&1; then
    run "cp '$REPO/bundle/fonts/macos/'*.ttf browser/fonts/"
    # Idempotency guard: the standard flow runs this script twice (make setup
    # bakes it into the `unpatched` tag, then make dir re-runs it), so appending
    # unconditionally would duplicate the FINAL_TARGET_FILES.fonts entries and
    # fail mozbuild with "Item already in manifest". Only append once.
    if grep -q "Cloakfox: bundled open-substitute font pack" browser/fonts/moz.build; then
        echo "Bundled font install rule already present in browser/fonts/moz.build; skipping append."
    else
        {
            echo ""
            echo "# Cloakfox: bundled open-substitute font pack (all platforms)."
            echo 'DIST_SUBDIR = ""'
            echo "FINAL_TARGET_FILES.fonts += ["
            for f in "$REPO/bundle/fonts/macos/"*.ttf; do
                echo "    \"$(basename "$f")\","
            done
            echo "]"
        } >> browser/fonts/moz.build
        echo "Staged $(ls "$REPO/bundle/fonts/macos/"*.ttf | wc -l | tr -d ' ') bundled fonts into browser/fonts/"
    fi
fi

# Override the firefox version
for file in "browser/config/version.txt" "browser/config/version_display.txt"; do
    echo "${version}-${release}" > "$file"
done

echo "Additions and settings copied successfully."
