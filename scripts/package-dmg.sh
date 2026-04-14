#!/usr/bin/env bash
set -euo pipefail

FIREFOX_SRC="${1:-firefox-src}"
APP_NAME="Cloakfox"
DMG_NAME="cloakfox.dmg"

# Find the built .app bundle
OBJ_DIR=$(find "$FIREFOX_SRC" -maxdepth 1 -type d -name 'obj-*' | head -1)
if [[ -z "$OBJ_DIR" ]]; then
    echo "Error: No build output found. Run 'make build' first."
    exit 1
fi

APP_BUNDLE="$OBJ_DIR/dist/${APP_NAME}.app"
if ! [[ -d "$APP_BUNDLE" ]]; then
    # Fall back to default Firefox name
    APP_BUNDLE="$OBJ_DIR/dist/Firefox.app"
fi

if ! [[ -d "$APP_BUNDLE" ]]; then
    echo "Error: App bundle not found at expected paths."
    echo "Looked in: $OBJ_DIR/dist/"
    ls "$OBJ_DIR/dist/" 2>/dev/null || true
    exit 1
fi

echo "Creating DMG from $APP_BUNDLE..."

# Create a temporary directory for the DMG contents
STAGING=$(mktemp -d)
cp -R "$APP_BUNDLE" "$STAGING/"
ln -s /Applications "$STAGING/Applications"

# Create DMG
hdiutil create -volname "$APP_NAME" \
    -srcfolder "$STAGING" \
    -ov -format UDZO \
    "$DMG_NAME"

rm -rf "$STAGING"

echo "DMG created: $DMG_NAME"
