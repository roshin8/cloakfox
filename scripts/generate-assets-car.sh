#!/bin/bash
# Produces additions/browser/branding/cloakfox/Assets.car (the macOS app-icon
# asset catalog) and syncs it into any extracted build tree.
#
# When full Xcode is present, the real Cloakfox icon is compiled from the
# branding PNGs with actool. Otherwise this falls back to the placeholder
# Assets.car shipped by Firefox's "official" branding — the icon is wrong but
# the build/package never hard-fails over a cosmetic asset. Re-run once you
# have full Xcode (`sudo xcode-select -s /Applications/Xcode.app`) to swap in
# the real icon.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BRANDING_DIR="$REPO_DIR/additions/browser/branding/cloakfox"
XCASSETS_DIR="$BRANDING_DIR/Assets.xcassets"
APPICONSET_DIR="$XCASSETS_DIR/AppIcon.appiconset"
OUTPUT_FILE="$BRANDING_DIR/Assets.car"

# Copy a prebuilt Assets.car from Firefox's official branding as a placeholder.
# The extracted source dir is normally firefox-src, but older layouts named it
# cloakfox-<version>; try both. Returns non-zero only if nothing is found.
place_placeholder() {
    local cand
    for cand in \
        "$REPO_DIR/firefox-src/browser/branding/official/Assets.car" \
        $REPO_DIR/cloakfox-*/browser/branding/official/Assets.car; do
        if [[ -f "$cand" ]]; then
            cp "$cand" "$OUTPUT_FILE"
            echo "Assets.car: using placeholder icon from $cand"
            return 0
        fi
    done
    echo "Assets.car: no placeholder found (looked under firefox-src/ and" \
         "cloakfox-*/ official branding). Run 'make fetch setup-minimal' first."
    return 1
}

# Mirror the produced Assets.car into any already-extracted build tree so the
# next ./mach package picks it up without a re-copy of additions/.
sync_into_src() {
    local srcbrand
    for srcbrand in \
        "$REPO_DIR/firefox-src/browser/branding/cloakfox" \
        $REPO_DIR/cloakfox-*/browser/branding/cloakfox; do
        if [[ -d "$srcbrand" ]]; then
            cp "$OUTPUT_FILE" "$srcbrand/Assets.car"
            echo "Assets.car: synced into $srcbrand"
        fi
    done
}

# Resolve actool (ships only with full Xcode, not the Command Line Tools).
# A shim may exist on PATH even without Xcode, so pre-flight that it actually
# runs — otherwise we'd churn the source PNGs before failing on the compile.
ACTOOL="$(xcrun --find actool 2>/dev/null || true)"
[[ -z "$ACTOOL" ]] && command -v actool &>/dev/null && ACTOOL="actool"
if [[ -n "$ACTOOL" ]] && ! "$ACTOOL" --version &>/dev/null; then
    ACTOOL=""
fi

if [[ "$(uname)" != "Darwin" || -z "$ACTOOL" ]]; then
    if [[ "$(uname)" != "Darwin" ]]; then
        echo "Assets.car: not macOS — actool unavailable, using placeholder."
    else
        echo "Assets.car: full Xcode not found (only Command Line Tools);" \
             "using placeholder. Install Xcode to compile the real icon."
    fi
    place_placeholder || exit 1
    sync_into_src
    exit 0
fi

echo "Generating Assets.car from cloakfox branding icons with $ACTOOL ..."

# Create xcassets structure
mkdir -p "$APPICONSET_DIR"

# Create Contents.json for the asset catalog
cat > "$XCASSETS_DIR/Contents.json" << 'EOF'
{
  "info" : {
    "author" : "xcode",
    "version" : 1
  }
}
EOF

# Create Contents.json for AppIcon with all icon sizes macOS needs
cat > "$APPICONSET_DIR/Contents.json" << 'EOF'
{
  "images" : [
    {
      "filename" : "icon_16x16.png",
      "idiom" : "mac",
      "scale" : "1x",
      "size" : "16x16"
    },
    {
      "filename" : "icon_16x16@2x.png",
      "idiom" : "mac",
      "scale" : "2x",
      "size" : "16x16"
    },
    {
      "filename" : "icon_32x32.png",
      "idiom" : "mac",
      "scale" : "1x",
      "size" : "32x32"
    },
    {
      "filename" : "icon_32x32@2x.png",
      "idiom" : "mac",
      "scale" : "2x",
      "size" : "32x32"
    },
    {
      "filename" : "icon_128x128.png",
      "idiom" : "mac",
      "scale" : "1x",
      "size" : "128x128"
    },
    {
      "filename" : "icon_128x128@2x.png",
      "idiom" : "mac",
      "scale" : "2x",
      "size" : "128x128"
    },
    {
      "filename" : "icon_256x256.png",
      "idiom" : "mac",
      "scale" : "1x",
      "size" : "256x256"
    },
    {
      "filename" : "icon_256x256@2x.png",
      "idiom" : "mac",
      "scale" : "2x",
      "size" : "256x256"
    },
    {
      "filename" : "icon_512x512.png",
      "idiom" : "mac",
      "scale" : "1x",
      "size" : "512x512"
    },
    {
      "filename" : "icon_512x512@2x.png",
      "idiom" : "mac",
      "scale" : "2x",
      "size" : "512x512"
    }
  ],
  "info" : {
    "author" : "xcode",
    "version" : 1
  }
}
EOF

# Copy/resize icons to the required sizes using sips (macOS built-in).
copy_or_resize() {
    local src="$1"
    local dst="$2"
    local size="$3"

    if [[ -f "$src" ]]; then
        cp "$src" "$dst"
        sips -z "$size" "$size" "$dst" >/dev/null 2>&1 || true
    elif [[ -f "$BRANDING_DIR/default256.png" ]]; then
        # Fallback to default256 and resize
        cp "$BRANDING_DIR/default256.png" "$dst"
        sips -z "$size" "$size" "$dst" >/dev/null 2>&1 || true
    fi
}

# Map branding icons to xcassets icons
copy_or_resize "$BRANDING_DIR/default16.png" "$APPICONSET_DIR/icon_16x16.png" 16
copy_or_resize "$BRANDING_DIR/default32.png" "$APPICONSET_DIR/icon_16x16@2x.png" 32
copy_or_resize "$BRANDING_DIR/default32.png" "$APPICONSET_DIR/icon_32x32.png" 32
copy_or_resize "$BRANDING_DIR/default64.png" "$APPICONSET_DIR/icon_32x32@2x.png" 64
copy_or_resize "$BRANDING_DIR/default128.png" "$APPICONSET_DIR/icon_128x128.png" 128
copy_or_resize "$BRANDING_DIR/default256.png" "$APPICONSET_DIR/icon_128x128@2x.png" 256
copy_or_resize "$BRANDING_DIR/default256.png" "$APPICONSET_DIR/icon_256x256.png" 256
copy_or_resize "$BRANDING_DIR/default256.png" "$APPICONSET_DIR/icon_256x256@2x.png" 512
copy_or_resize "$BRANDING_DIR/default256.png" "$APPICONSET_DIR/icon_512x512.png" 512
copy_or_resize "$BRANDING_DIR/default256.png" "$APPICONSET_DIR/icon_512x512@2x.png" 1024

# Generate Assets.car using actool. If actool fails for any reason, fall back
# to the placeholder rather than aborting the whole build.
TEMP_DIR="$(mktemp -d)"
if "$ACTOOL" \
    --compile "$TEMP_DIR" \
    --platform macosx \
    --minimum-deployment-target 10.15 \
    --app-icon AppIcon \
    --output-partial-info-plist "$TEMP_DIR/Info.plist" \
    "$XCASSETS_DIR" && [[ -f "$TEMP_DIR/Assets.car" ]]; then
    mv "$TEMP_DIR/Assets.car" "$OUTPUT_FILE"
    echo "Successfully generated real icon: $OUTPUT_FILE"
else
    echo "Assets.car: actool failed; falling back to placeholder icon."
    place_placeholder || { rm -rf "$TEMP_DIR"; exit 1; }
fi
rm -rf "$TEMP_DIR"

sync_into_src
echo "Done!"
