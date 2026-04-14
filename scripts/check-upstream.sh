#!/usr/bin/env bash
set -euo pipefail

# Check for new Cloakfox releases and show what changed in patches
source UPSTREAM_VERSION

echo "Current pinned version: $CLOAKFOX_TAG"
echo "Checking for updates..."

LATEST=$(curl -s "https://api.github.com/repos/nicholasgcoles/cloakfox/releases/latest" | \
    grep '"tag_name"' | sed -E 's/.*"([^"]+)".*/\1/')

if [[ -z "$LATEST" ]]; then
    echo "Error: Could not fetch latest release."
    exit 1
fi

echo "Latest upstream release: $LATEST"

if [[ "$LATEST" == "$CLOAKFOX_TAG" ]]; then
    echo "Already up to date."
else
    echo ""
    echo "New version available: $LATEST"
    echo "Review changes: https://github.com/nicholasgcoles/cloakfox/compare/${CLOAKFOX_TAG}...${LATEST}"
    echo ""
    echo "To update:"
    echo "  1. Update CLOAKFOX_TAG in UPSTREAM_VERSION"
    echo "  2. Download new patches and compare with existing"
    echo "  3. Run 'make clean && make fetch && make patch' to test"
fi
