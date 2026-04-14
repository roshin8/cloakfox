#!/usr/bin/env bash
set -euo pipefail

FIREFOX_VERSION="${1:?Usage: fetch-firefox.sh <version>}"
ARCHIVE="firefox-${FIREFOX_VERSION}.source.tar.xz"
URL="https://archive.mozilla.org/pub/firefox/releases/${FIREFOX_VERSION}/source/${ARCHIVE}"

if [[ -f "$ARCHIVE" ]]; then
    echo "Archive already downloaded: $ARCHIVE"
else
    echo "Downloading Firefox ${FIREFOX_VERSION} source..."
    if command -v aria2c &>/dev/null; then
        aria2c -x16 -s16 -k1M -o "$ARCHIVE" "$URL"
    else
        curl -L -o "$ARCHIVE" "$URL"
    fi
fi

echo "Firefox ${FIREFOX_VERSION} source tarball ready: $ARCHIVE"
