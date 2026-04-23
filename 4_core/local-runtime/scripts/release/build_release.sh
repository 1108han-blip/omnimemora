#!/bin/bash
# scripts/release/build_release.sh - Build closed beta release archives
set -euo pipefail

PACKAGE_VERSION=${1:-"1.0.0-beta.1"}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
RELEASE_DIR="$ROOT_DIR/release/$PACKAGE_VERSION"
SUPPORT_EMAIL=${OMNIMEMORA_BETA_SUPPORT_EMAIL:-"1108.han@gmail.com"}
DOWNLOAD_BASE_URL=${OMNIMEMORA_DOWNLOAD_BASE_URL:-"https://assets.doloclaw.com/omnimemora/beta/$PACKAGE_VERSION"}

echo "Building OmniMemora controlled beta package set: $PACKAGE_VERSION"

rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"

render_template() {
    local src="$1"
    local dest="$2"
    sed \
        -e "s|{{PACKAGE_VERSION}}|$PACKAGE_VERSION|g" \
        -e "s|{{SUPPORT_EMAIL}}|$SUPPORT_EMAIL|g" \
        -e "s|{{DOWNLOAD_BASE_URL}}|$DOWNLOAD_BASE_URL|g" \
        "$src" > "$dest"
}

build() {
    local goos="$1"
    local goarch="$2"
    local package_name="$3"
    local binary_name="omnimemora"

    if [ "$goos" = "windows" ]; then
        binary_name="omnimemora.exe"
    fi

    echo "Building $package_name ..."
    mkdir -p "$RELEASE_DIR/$package_name"

    (
        cd "$ROOT_DIR"
        GOOS="$goos" GOARCH="$goarch" go build -ldflags="-s -w" -o "$RELEASE_DIR/$package_name/$binary_name" .
    )

    render_template "$SCRIPT_DIR/README.txt" "$RELEASE_DIR/$package_name/README.txt"
    render_template "$SCRIPT_DIR/LICENSE.txt" "$RELEASE_DIR/$package_name/LICENSE.txt"
    render_template "$SCRIPT_DIR/BETA_TERMS.txt" "$RELEASE_DIR/$package_name/BETA_TERMS.txt"
    render_template "$SCRIPT_DIR/RELEASE_NOTES.txt" "$RELEASE_DIR/$package_name/RELEASE_NOTES.txt"
    render_template "$SCRIPT_DIR/KNOWN_ISSUES.txt" "$RELEASE_DIR/$package_name/KNOWN_ISSUES.txt"

    cat > "$RELEASE_DIR/$package_name/VERSION.txt" <<EOF
PACKAGE_VERSION=$PACKAGE_VERSION
CHANNEL=controlled-beta
SUPPORT_EMAIL=$SUPPORT_EMAIL
EOF

    (
        cd "$RELEASE_DIR"
        zip -rq "$package_name.zip" "$package_name"
        shasum -a 256 "$package_name.zip" >> SHA256SUMS.txt
    )
}

build "darwin" "amd64" "omnimemora-darwin-amd64"
build "darwin" "arm64" "omnimemora-darwin-arm64"
build "windows" "amd64" "omnimemora-windows-amd64"

cat > "$RELEASE_DIR/RELEASE_INDEX.txt" <<EOF
OmniMemora Controlled Beta
Package version: $PACKAGE_VERSION
Channel: controlled-beta
Download base: $DOWNLOAD_BASE_URL
Support: $SUPPORT_EMAIL
EOF

echo ""
echo "Release build complete: $RELEASE_DIR"
ls -la "$RELEASE_DIR"
