#!/bin/bash

# Container Shield - AMO Packaging Script
# Creates a signed-ready XPI package for Firefox Add-ons

set -e

echo "📦 Container Shield Packaging Script"
echo "======================================"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get version from manifest
VERSION=$(grep '"version"' manifest.json | head -1 | sed 's/.*: "\(.*\)".*/\1/')
echo -e "${GREEN}Version: $VERSION${NC}"

# Build directory
BUILD_DIR="dist"
PACKAGE_DIR="packages"
PACKAGE_NAME="containershield-${VERSION}"

# Check if dist exists
if [ ! -d "$BUILD_DIR" ]; then
    echo -e "${YELLOW}Building extension first...${NC}"
    npm run build
fi

# Create packages directory
mkdir -p "$PACKAGE_DIR"

# Remove old package if exists
rm -f "$PACKAGE_DIR/$PACKAGE_NAME.zip"
rm -f "$PACKAGE_DIR/$PACKAGE_NAME.xpi"

echo -e "${YELLOW}Creating package...${NC}"

# Create zip file for AMO submission
cd "$BUILD_DIR"
zip -r "../$PACKAGE_DIR/$PACKAGE_NAME.zip" . -x "*.DS_Store" -x "__MACOSX/*"
cd ..

# Copy as XPI (Firefox extension format)
cp "$PACKAGE_DIR/$PACKAGE_NAME.zip" "$PACKAGE_DIR/$PACKAGE_NAME.xpi"

# Calculate file sizes
ZIP_SIZE=$(du -h "$PACKAGE_DIR/$PACKAGE_NAME.zip" | cut -f1)
XPI_SIZE=$(du -h "$PACKAGE_DIR/$PACKAGE_NAME.xpi" | cut -f1)

echo ""
echo -e "${GREEN}✅ Package created successfully!${NC}"
echo ""
echo "📁 Output files:"
echo "   $PACKAGE_DIR/$PACKAGE_NAME.zip ($ZIP_SIZE)"
echo "   $PACKAGE_DIR/$PACKAGE_NAME.xpi ($XPI_SIZE)"
echo ""
echo "📋 Next steps:"
echo "   1. Test locally: about:debugging > Load Temporary Add-on > select dist/manifest.json"
echo "   2. Submit to AMO: https://addons.mozilla.org/developers/"
echo "   3. Upload the .zip file for review"
echo ""
echo "📝 For self-distribution (unsigned):"
echo "   - Enable xpinstall.signatures.required = false in about:config"
echo "   - Drag .xpi file into Firefox"
echo ""
echo -e "${YELLOW}Note: For AMO signing, you'll need a Mozilla Add-ons developer account.${NC}"
