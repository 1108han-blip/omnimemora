#!/bin/bash
# scripts/release/build_release.sh - Build closed beta release archives
set -euo pipefail

PACKAGE_VERSION=${1:-"1.0.0-beta.2"}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
RELEASE_DIR="$ROOT_DIR/release/$PACKAGE_VERSION"
SUPPORT_EMAIL=${OMNIMEMORA_BETA_SUPPORT_EMAIL:-"support@doloclaw.com"}
DOWNLOAD_BASE_URL=${OMNIMEMORA_DOWNLOAD_BASE_URL:-"https://assets.doloclaw.com/omnimemora/beta/$PACKAGE_VERSION"}
PUBLISHED_AT=${OMNIMEMORA_RELEASE_PUBLISHED_AT:-"$(date -u +"%Y-%m-%dT%H:%M:%SZ")"}

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

sha_for() {
    local filename="$1"
    awk -v name="$filename" '$2 == name {print $1}' "$RELEASE_DIR/SHA256SUMS.txt"
}

write_release_manifest() {
    local manifest_path="$RELEASE_DIR/$PACKAGE_VERSION.json"
    local darwin_arm64_sha
    local darwin_amd64_sha
    local windows_amd64_sha

    darwin_arm64_sha="$(sha_for omnimemora-darwin-arm64.zip)"
    darwin_amd64_sha="$(sha_for omnimemora-darwin-amd64.zip)"
    windows_amd64_sha="$(sha_for omnimemora-windows-amd64.zip)"

    cat > "$manifest_path" <<EOF
{
  "product": "omnimemora",
  "channel": "desktop-beta",
  "version": "$PACKAGE_VERSION",
  "published_at": "$PUBLISHED_AT",
  "platforms": {
    "darwin-arm64": {
      "package": "omnimemora-darwin-arm64.zip",
      "sha256": "$darwin_arm64_sha",
      "download_url": "https://doloclaw.com/download/file/darwin-arm64"
    },
    "darwin-amd64": {
      "package": "omnimemora-darwin-amd64.zip",
      "sha256": "$darwin_amd64_sha",
      "download_url": "https://doloclaw.com/download/file/darwin-amd64"
    },
    "windows-amd64": {
      "package": "omnimemora-windows-amd64.zip",
      "sha256": "$windows_amd64_sha",
      "download_url": "https://doloclaw.com/download/file/windows-amd64"
    }
  },
  "components": {
    "desktop_shell": {
      "framework": "tauri",
      "update_mode": "manual_installer_prompt"
    },
    "runtime": {
      "port": 8765,
      "role": "internal_memory_plane"
    },
    "adapter": {
      "port": 18011,
      "role": "product_ingress_after_opt_in"
    },
    "ui": {
      "port": 5173,
      "role": "user_control_display"
    },
    "cloud_policy": {
      "mode": "candidate",
      "auto_promote": false
    }
  },
  "sha256": {
    "darwin-arm64": "$darwin_arm64_sha",
    "darwin-amd64": "$darwin_amd64_sha",
    "windows-amd64": "$windows_amd64_sha"
  },
  "download_url": "https://doloclaw.com/download",
  "release_notes": "Desktop beta foundation: tracked installer downloads, release manifest, local component update metadata, and candidate-only cloud policy update posture.",
  "minimum_supported_desktop_version": "1.0.0-beta.2",
  "force_update": false
}
EOF
    cp "$manifest_path" "$RELEASE_DIR/latest.json"
}

write_release_manifest

cat > "$RELEASE_DIR/RELEASE_INDEX.txt" <<EOF
OmniMemora Desktop Beta
Package version: $PACKAGE_VERSION
Channel: desktop-beta
Download base: $DOWNLOAD_BASE_URL
Support: $SUPPORT_EMAIL
Latest manifest: https://doloclaw.com/releases/latest.json
EOF

echo ""
echo "Release build complete: $RELEASE_DIR"
ls -la "$RELEASE_DIR"
