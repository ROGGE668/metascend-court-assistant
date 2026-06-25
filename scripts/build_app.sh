#!/bin/bash
set -e
echo "--- Building frontend and packaging macOS app ---"
cd "$(dirname "$0")/../frontend"

npm run build
npx tauri build --no-sign "$@"

APP="src-tauri/target/release/bundle/macos/Metascend Court Assistant.app"
if [ -d "$APP" ]; then
    echo "--- Patching Info.plist ---"
    plutil -replace LSRequiresCarbon -bool false "$APP/Contents/Info.plist"
    plutil -replace LSMinimumSystemVersion -string "14.0" "$APP/Contents/Info.plist"
    echo "--- Info.plist patched successfully ---"
    plutil -p "$APP/Contents/Info.plist" | sed -n '1,20p'
fi
