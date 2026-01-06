#!/usr/bin/env bash
set -euo pipefail

VERSION="${MEDIAMTX_VERSION:-v1.15.6}"
BASE_URL="${MEDIAMTX_BASE_URL:-https://github.com/bluenviron/mediamtx/releases/download}"

OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS" in
  Linux) PLATFORM="linux" ;;
  Darwin) PLATFORM="darwin" ;;
  MINGW*|MSYS*|CYGWIN*) PLATFORM="windows" ;;
  *) echo "Unsupported OS: $OS" >&2; exit 1 ;;
esac

case "$ARCH" in
  x86_64|amd64) ARCH_LABEL="amd64" ;;
  arm64|aarch64) ARCH_LABEL="arm64" ;;
  *) echo "Unsupported arch: $ARCH" >&2; exit 1 ;;
esac

ASSET="mediamtx_${VERSION}_${PLATFORM}_${ARCH_LABEL}"
EXT="tar.gz"
BIN="mediamtx"

if [ "$PLATFORM" = "windows" ]; then
  EXT="zip"
  BIN="mediamtx.exe"
fi

ARCHIVE="${ASSET}.${EXT}"
URL="${BASE_URL}/${VERSION}/${ARCHIVE}"

echo "Downloading ${URL}"

TMP_DIR="$(mktemp -d)"
cleanup() { rm -rf "$TMP_DIR"; }
trap cleanup EXIT

if command -v curl >/dev/null 2>&1; then
  curl -fsSL "$URL" -o "$TMP_DIR/$ARCHIVE"
elif command -v wget >/dev/null 2>&1; then
  wget -qO "$TMP_DIR/$ARCHIVE" "$URL"
else
  echo "curl or wget is required." >&2
  exit 1
fi

if [ "$EXT" = "zip" ]; then
  if ! command -v unzip >/dev/null 2>&1; then
    echo "unzip is required for Windows archives." >&2
    exit 1
  fi
  unzip -q "$TMP_DIR/$ARCHIVE" -d "$TMP_DIR"
else
  tar -xzf "$TMP_DIR/$ARCHIVE" -C "$TMP_DIR"
fi

if [ ! -f "$TMP_DIR/$BIN" ]; then
  echo "Expected binary not found in archive: $BIN" >&2
  exit 1
fi

install -m 0755 "$TMP_DIR/$BIN" "$(dirname "$0")/$BIN"
echo "Installed $(dirname "$0")/$BIN"
