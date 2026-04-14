#!/bin/bash
# scripts/release/build_release.sh - Build release binaries for all platforms
set -e

VERSION=${1:-"1.0.0"}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
RELEASE_DIR="$ROOT_DIR/release"

echo "Building OmniMemora v$VERSION release packages..."

# Clean previous releases
rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"

# Build function
build() {
    local GOOS=$1
    local GOARCH=$2
    local OUTPUT_NAME=$3

    echo "Building $OUTPUT_NAME..."

    cd "$ROOT_DIR"
    GOOS=$GOOS GOARCH=$GOARCH go build -ldflags="-s -w" -o "$RELEASE_DIR/$OUTPUT_NAME/omnimemora" ./cmd/omnimemora/

    # Copy README
    cp "$SCRIPT_DIR/README.txt" "$RELEASE_DIR/$OUTPUT_NAME/"
    cp "$SCRIPT_DIR/LICENSE.txt" "$RELEASE_DIR/$OUTPUT_NAME/"

    # Create zip
    cd "$RELEASE_DIR"
    if [ "$GOOS" = "windows" ]; then
        powershell -Command "Compress-Archive -Path '$OUTPUT_NAME/*' -DestinationPath '$OUTPUT_NAME.zip' -Force"
    else
        zip -r "$OUTPUT_NAME.zip" "$OUTPUT_NAME"
    fi

    echo "Created $OUTPUT_NAME.zip"
}

# Create directories
mkdir -p "$RELEASE_DIR/omnimemora-darwin-amd64"
mkdir -p "$RELEASE_DIR/omnimemora-darwin-arm64"
mkdir -p "$RELEASE_DIR/omnimemora-windows-amd64"

# Build for each platform
build darwin amd64 omnimemora-darwin-amd64
build darwin arm64 omnimemora-darwin-arm64
build windows amd64 omnimemora-windows-amd64

echo ""
echo "Release build complete!"
echo "Output directory: $RELEASE_DIR"
ls -la "$RELEASE_DIR"
