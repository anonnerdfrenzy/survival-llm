#!/bin/bash
# Build the downloadable apps (run on a Mac with Xcode's command-line tools): a Mac app for Apple Silicon and a
# Windows folder. Each bundles a portable Python (python-build-standalone), pywebview for the app window, and the
# app code. The Mac app also carries Ollama (the AI engine); the Windows one downloads it on first use, since
# Ollama for Windows is 1.6 GB. The AI model and the library are downloaded from inside the app.
# Output: dist/Survival-LLM-mac.zip and dist/Survival-LLM-windows.zip
#   build.sh mac   only the Mac app (dist/mac and its zip), as bin/dev --release runs it
#   build.sh dev   only "Survival LLM Dev" in ~/Applications: the Mac app running the code in this folder (bin/dev)
set -euo pipefail
TARGET="${1:-all}"
case "$TARGET" in all|mac|dev) ;; *) echo "usage: packaging/build.sh [mac|dev]" >&2; exit 2 ;; esac

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(dirname "$HERE")"
CACHE="$HERE/cache"
DIST="$REPO/dist"
VERSION="$(cat "$HERE/VERSION")"
PBS_TAG="20261021"
PBS_PY="3.12.15"
PBS_URL="https://github.com/astral-sh/python-build-standalone/releases/download/$PBS_TAG"
OLLAMA_VERSION="v0.40.11"
OLLAMA_URL="https://github.com/ollama/ollama/releases/download/$OLLAMA_VERSION"
PYWEBVIEW="pywebview==6.2.1"
PYPDF="pypdf==6.19.0"  # reads the PDFs people add to their own files (pure Python, same for Mac and Windows)
TRUSTSTORE="truststore==0.10.4"  # checks web certificates with the system's own store (pure Python)

mkdir -p "$CACHE" "$DIST"

fetch_python() {  # $1 = target triple
  local file="cpython-$PBS_PY+$PBS_TAG-$1-install_only_stripped.tar.gz"
  [ -f "$CACHE/$file" ] || curl -L --fail -sS -o "$CACHE/$file" "$PBS_URL/$file"
  echo "$CACHE/$file"
}

copy_app() {  # $1 = destination folder for the app code
  mkdir -p "$1/library" "$1/app/static"
  cp "$REPO/core.py" "$REPO/memory.py" "$1/"
  cp "$REPO/library/search.py" "$REPO/library/passages.py" "$REPO/library/myfiles.py" "$1/library/"
  cp "$REPO/app/server.py" "$1/app/"
  cp "$REPO/app/static/"* "$1/app/static/"
  cp "$REPO/LICENSE" "$REPO/README.md" "$REPO/SOURCES.md" "$1/"
  echo "$VERSION" > "$1/version.txt"  # the app compares it with the published update.json
}

fetch_ollama() {  # $1 = release file name; checked against Ollama's published checksums
  local file="ollama-$OLLAMA_VERSION-$1"
  [ -f "$CACHE/ollama-sha256-$OLLAMA_VERSION.txt" ] || curl -L --fail -sS -o "$CACHE/ollama-sha256-$OLLAMA_VERSION.txt" "$OLLAMA_URL/sha256sum.txt"
  [ -f "$CACHE/$file" ] || curl -L --fail -sS -o "$CACHE/$file" "$OLLAMA_URL/$1"
  local want; want="$(grep " \./$1\$" "$CACHE/ollama-sha256-$OLLAMA_VERSION.txt" | cut -d' ' -f1)"
  [ "$(shasum -a 256 "$CACHE/$file" | cut -d' ' -f1)" = "$want" ] || { echo "checksum mismatch: $file" >&2; exit 1; }
  echo "$CACHE/$file"
}

info_plist() {  # $1 = app name (also its executable's), $2 = bundle id
  cat <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>$1</string>
  <key>CFBundleDisplayName</key><string>$1</string>
  <key>CFBundleIdentifier</key><string>$2</string>
  <key>CFBundleExecutable</key><string>$1</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>CFBundleVersion</key><string>$VERSION</string>
  <key>LSMinimumSystemVersion</key><string>14.0</string>
  <key>NSHighResolutionCapable</key><true/>
  $( [ -f "$HERE/AppIcon.icns" ] && echo "<key>CFBundleIconFile</key><string>AppIcon</string>" )
</dict></plist>
EOF
}

# ---------- dev copy: the Mac app running the code in this folder, as it is when it starts (bin/dev) ----------
# The same Python, pywebview, launcher and Ollama as the real app, but its code is a link to this folder, and it has
# its own name, settings, memory and files, so an installed Survival LLM stays as it is. Not signed or sealed: it is
# built on this Mac, so macOS runs it as is.
if [ "$TARGET" = dev ]; then
  DEV_APP="$HOME/Applications/Survival LLM Dev.app"
  DEV_RES="$DEV_APP/Contents/Resources"
  PROFILE="$HOME/Library/Application Support/Survival LLM Dev"
  rm -rf "$DEV_APP"
  mkdir -p "$DEV_APP/Contents/MacOS" "$DEV_RES/ollama"
  tar -xzf "$(fetch_python aarch64-apple-darwin)" -C "$DEV_RES"
  "$DEV_RES/python/bin/python3" -m pip install -q --no-compile --disable-pip-version-check "$PYWEBVIEW" "$PYPDF" "$TRUSTSTORE"
  rm -rf "$DEV_RES/python/lib/python3.12/site-packages/PyObjCTest"
  tar -xzf "$(fetch_ollama ollama-darwin.tgz)" -C "$DEV_RES/ollama"
  ln -s "$REPO" "$DEV_RES/app"
  clang -O2 -arch arm64 -mmacosx-version-min=14.0 -DSURVIVAL_LLM_DEV "$HERE/launcher.c" \
    -o "$DEV_APP/Contents/MacOS/Survival LLM Dev" -I"$DEV_RES/python/include/python3.12" -L"$DEV_RES/python/lib" \
    -lpython3.12 -Wl,-rpath,@executable_path/../Resources/python/lib
  printf '%s\n' "SURVIVAL_LLM_DEV=1" "SURVIVAL_LLM_APP_DIR=$PROFILE" "SURVIVAL_LLM_FILES=$PROFILE/files" > "$DEV_RES/dev.env"
  info_plist "Survival LLM Dev" org.survival-llm.dev > "$DEV_APP/Contents/Info.plist"
  [ -f "$HERE/AppIcon.icns" ] && cp "$HERE/AppIcon.icns" "$DEV_RES/"
  echo "Built $DEV_APP"
  exit 0
fi

# ---------- macOS (Apple Silicon) ----------
APP="$DIST/mac/Survival LLM.app"
RES="$APP/Contents/Resources"
rm -rf "$DIST/mac"
mkdir -p "$APP/Contents/MacOS" "$RES"
tar -xzf "$(fetch_python aarch64-apple-darwin)" -C "$RES"
"$RES/python/bin/python3" -m pip install -q --no-compile --disable-pip-version-check "$PYWEBVIEW" "$PYPDF" "$TRUSTSTORE"
rm -rf "$RES/python/lib/python3.12/site-packages/PyObjCTest"  # pyobjc's own test suite
copy_app "$RES/app"
clang -O2 -arch arm64 -mmacosx-version-min=14.0 "$HERE/launcher.c" -o "$APP/Contents/MacOS/Survival LLM" \
  -I"$RES/python/include/python3.12" -L"$RES/python/lib" -lpython3.12 \
  -Wl,-rpath,@executable_path/../Resources/python/lib
info_plist "Survival LLM" org.survival-llm.app > "$APP/Contents/Info.plist"
[ -f "$HERE/AppIcon.icns" ] && cp "$HERE/AppIcon.icns" "$APP/Contents/Resources/"
xattr -cr "$APP"  # no stray extended attributes in the zip (other unzippers turn them into files that break the seal)
codesign --force --deep --sign - "$APP" 2>/dev/null   # ad-hoc signature; Apple Silicon refuses unsigned code
# Ollama goes in after that, keeping its own Developer ID signature: macOS then runs it without a prompt even from
# a downloaded copy. Re-sealing the app (not --deep) records its files without re-signing them.
mkdir -p "$RES/ollama"
tar -xzf "$(fetch_ollama ollama-darwin.tgz)" -C "$RES/ollama"
codesign --force --sign - "$APP"
rm -f "$DIST/Survival-LLM-mac.zip"
(cd "$DIST/mac" && ditto -c -k --norsrc --noextattr --keepParent "Survival LLM.app" "$DIST/Survival-LLM-mac.zip")
if [ "$TARGET" = mac ]; then
  ls -lh "$DIST/Survival-LLM-mac.zip"
  exit 0
fi

# ---------- Windows (x64) ----------
WIN="$DIST/windows/Survival LLM"
rm -rf "$DIST/windows"
mkdir -p "$WIN"
tar -xzf "$(fetch_python x86_64-pc-windows-msvc)" -C "$WIN"
# pip judges dependencies by the computer it runs on, so the Windows ones are named here; proxy_tools only exists
# as source, and it is plain Python, so the copy pip just made for the Mac is reused.
"$RES/python/bin/python3" -m pip install -q --no-compile --disable-pip-version-check --target "$WIN/python/Lib/site-packages" \
  --platform win_amd64 --python-version 3.12 --implementation cp --only-binary=:all: --no-deps \
  "$PYWEBVIEW" "$PYPDF" "$TRUSTSTORE" pythonnet==3.2.1 clr_loader==0.3.1 cffi==2.1.1 pycparser bottle typing_extensions
cp -R "$RES/python/lib/python3.12/site-packages/proxy_tools" "$WIN/python/Lib/site-packages/"
copy_app "$WIN/app"
# Microsoft's WebView2 installer (about 2 MB, free to ship with apps): the app runs it on a PC without WebView2, which
# the app window needs (issue #17). It fetches the current WebView2 itself, so this file rarely needs refreshing.
WV2="$CACHE/MicrosoftEdgeWebview2Setup.exe"
[ -f "$WV2" ] || curl -L --fail -sS -o "$WV2" "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
[ "$(head -c 2 "$WV2")" = "MZ" ] || { echo "not a Windows program: $WV2" >&2; rm -f "$WV2"; exit 1; }
cp "$WV2" "$WIN/app/"
# Where the app fetches Ollama on first use (checked against Ollama's published checksum).
"$RES/python/bin/python3" - "$CACHE/ollama-sha256-$OLLAMA_VERSION.txt" "$OLLAMA_URL/ollama-windows-amd64.zip" \
  "$WIN/app/engine.json" <<'PY'
import json, sys, urllib.request
sums, url, out = sys.argv[1:]
name = url.rsplit("/", 1)[1]
sha = next(line.split()[0] for line in open(sums) if line.split()[1] == "./" + name)
size = int(urllib.request.urlopen(urllib.request.Request(url, method="HEAD")).headers["Content-Length"])
json.dump({"url": url, "bytes": size, "sha256": sha, "version": url.split("/")[-2]}, open(out, "w"), indent=1)
PY
# pythonw runs without a console window; this .bat only starts it and closes.
printf '%s\r\n' \
  '@echo off' \
  'start "" /D "%USERPROFILE%" "%~dp0python\pythonw.exe" "%~dp0app\app\server.py"' > "$WIN/Survival LLM.bat"
(cd "$DIST/windows" && rm -f "$DIST/Survival-LLM-windows.zip" && zip -qr "$DIST/Survival-LLM-windows.zip" "Survival LLM")

ls -lh "$DIST"/*.zip
