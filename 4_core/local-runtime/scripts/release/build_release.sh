#!/bin/bash
# scripts/release/build_release.sh - Build closed beta release archives
set -euo pipefail

PACKAGE_VERSION=${1:-"1.0.0-beta.2"}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPO_ROOT="$(cd "$ROOT_DIR/../.." && pwd)"
RELEASE_DIR="$ROOT_DIR/release/$PACKAGE_VERSION"
SUPPORT_EMAIL=${OMNIMEMORA_BETA_SUPPORT_EMAIL:-"support@doloclaw.com"}
DOWNLOAD_BASE_URL=${OMNIMEMORA_DOWNLOAD_BASE_URL:-"https://assets.doloclaw.com/omnimemora/beta/$PACKAGE_VERSION"}
PUBLISHED_AT=${OMNIMEMORA_RELEASE_PUBLISHED_AT:-"$(date -u +"%Y-%m-%dT%H:%M:%SZ")"}

echo "Building OmniMemora controlled beta package set: $PACKAGE_VERSION"

rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"

require_path() {
    local path="$1"
    local message="$2"
    if [ ! -e "$path" ]; then
        echo "Missing required release input: $path" >&2
        echo "$message" >&2
        exit 1
    fi
}

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
    local platform_id="$4"
    local binary_name="omnimemora"

    if [ "$goos" = "windows" ]; then
        binary_name="omnimemora.exe"
    fi

    echo "Building $package_name ..."
    mkdir -p \
        "$RELEASE_DIR/$package_name/bin" \
        "$RELEASE_DIR/$package_name/tools" \
        "$RELEASE_DIR/$package_name/ui" \
        "$RELEASE_DIR/$package_name/4_core" \
        "$RELEASE_DIR/$package_name/5_connectors"

    (
        cd "$ROOT_DIR"
        GOOS="$goos" GOARCH="$goarch" go build -ldflags="-s -w" -o "$RELEASE_DIR/$package_name/bin/$binary_name" .
    )

    require_path "$REPO_ROOT/tools/_run_adapter.py" "Adapter launcher is required for desktop-managed startup."
    require_path "$REPO_ROOT/4_core/logic" "Adapter imports require packaged 4_core/logic source."
    require_path "$REPO_ROOT/5_connectors/adapter" "Adapter source is required for desktop-managed startup."
    require_path "$REPO_ROOT/6_console/demo-dashboard/dist/index.html" "Build 6_console/demo-dashboard before release packaging."

    cp "$REPO_ROOT/tools/_run_adapter.py" "$RELEASE_DIR/$package_name/tools/_run_adapter.py"
    rsync -a --delete \
        --exclude '__pycache__' \
        --exclude '.pytest_cache' \
        --exclude '__tests__' \
        --exclude 'tests' \
        "$REPO_ROOT/4_core/logic/" "$RELEASE_DIR/$package_name/4_core/logic/"
    rsync -a --delete \
        --exclude '__pycache__' \
        --exclude '.pytest_cache' \
        --exclude '__tests__' \
        --exclude 'tests' \
        --exclude 'backup_20260413' \
        --exclude 'data' \
        "$REPO_ROOT/5_connectors/adapter/" "$RELEASE_DIR/$package_name/5_connectors/adapter/"
    rsync -a --delete \
        "$REPO_ROOT/6_console/demo-dashboard/dist/" "$RELEASE_DIR/$package_name/ui/dist/"

    render_template "$SCRIPT_DIR/README.txt" "$RELEASE_DIR/$package_name/README.txt"
    render_template "$SCRIPT_DIR/LICENSE.txt" "$RELEASE_DIR/$package_name/LICENSE.txt"
    render_template "$SCRIPT_DIR/BETA_TERMS.txt" "$RELEASE_DIR/$package_name/BETA_TERMS.txt"
    render_template "$SCRIPT_DIR/RELEASE_NOTES.txt" "$RELEASE_DIR/$package_name/RELEASE_NOTES.txt"
    render_template "$SCRIPT_DIR/KNOWN_ISSUES.txt" "$RELEASE_DIR/$package_name/KNOWN_ISSUES.txt"

    cat > "$RELEASE_DIR/$package_name/VERSION.txt" <<EOF
PACKAGE_VERSION=$PACKAGE_VERSION
CHANNEL=controlled-beta
PLATFORM=$platform_id
SUPPORT_EMAIL=$SUPPORT_EMAIL
EOF

    cat > "$RELEASE_DIR/$package_name/manifest.json" <<EOF
{
  "product": "omnimemora",
  "channel": "desktop-beta",
  "version": "$PACKAGE_VERSION",
  "platform": "$platform_id",
  "published_at": "$PUBLISHED_AT",
  "layout": {
    "runtime_binary": "bin/$binary_name",
    "adapter_launcher": "tools/_run_adapter.py",
    "adapter_source": "5_connectors/adapter",
    "logic_source": "4_core/logic",
    "ui_dist": "ui/dist",
    "state_file": "desktop_state.json"
  },
  "components": {
    "desktop_shell": {
      "version": "$PACKAGE_VERSION",
      "update_mode": "manual_installer_prompt"
    },
    "runtime": {
      "version": "$PACKAGE_VERSION",
      "port": 8765,
      "role": "internal_memory_plane"
    },
    "adapter": {
      "version": "$PACKAGE_VERSION",
      "port": 18011,
      "role": "product_ingress_after_opt_in",
      "runtime_dependencies": "Python 3 with fastapi, uvicorn, pydantic, httpx, loguru"
    },
    "ui": {
      "version": "$PACKAGE_VERSION",
      "port": 5173,
      "role": "user_control_display"
    },
    "cloud_policy": {
      "mode": "candidate",
      "auto_promote": false
    }
  },
  "force_update": false
}
EOF

    (
        cd "$RELEASE_DIR"
        zip -rq "$package_name.zip" "$package_name"
        shasum -a 256 "$package_name.zip" >> SHA256SUMS.txt
    )
}

build "darwin" "amd64" "omnimemora-darwin-amd64" "darwin-amd64"
build "darwin" "arm64" "omnimemora-darwin-arm64" "darwin-arm64"
build "windows" "amd64" "omnimemora-windows-amd64" "windows-amd64"

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
