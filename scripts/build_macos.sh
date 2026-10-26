#!/bin/bash
# Build only: target Macs need neither Python nor developer tools.
set -euo pipefail
cd "$(dirname "$0")/.."
PROJECT="$PWD"
BUILD="$PROJECT/.build/macos"
DIST="$PROJECT/dist/macos"
PYTHON_VERSION=3.13.15
PYTHON_SHA=3b7eaf7f29825f796e8267024435540ddf1f17fc9a97ad58095daa7a75bfdcd3
mkdir -p "$BUILD" "$DIST"
if [ ! -f "$BUILD/python-$PYTHON_VERSION.pkg" ]; then
    curl -fL --retry 2 "https://www.python.org/ftp/python/$PYTHON_VERSION/python-$PYTHON_VERSION-macos11.pkg" -o "$BUILD/python-$PYTHON_VERSION.pkg"
fi
echo "$PYTHON_SHA  $BUILD/python-$PYTHON_VERSION.pkg" | shasum -a 256 -c -
if [ ! -d "$BUILD/python-package" ]; then
    pkgutil --expand-full "$BUILD/python-$PYTHON_VERSION.pkg" "$BUILD/python-package"
fi
mkdir -p "$BUILD/frameworks"
if [ ! -e "$BUILD/frameworks/Python.framework" ]; then
    ln -s ../python-package/Python_Framework.pkg/Payload "$BUILD/frameworks/Python.framework"
fi
export DYLD_FRAMEWORK_PATH="$BUILD/frameworks"
export DYLD_LIBRARY_PATH="$BUILD/frameworks/Python.framework/Versions/3.13/lib"
PYTHON="$BUILD/venv/bin/python"
if [ ! -x "$PYTHON" ]; then
    "$BUILD/frameworks/Python.framework/Versions/3.13/bin/python3.13" -m venv "$BUILD/venv"
fi
"$PYTHON" -m pip install 'pyinstaller==6.20.0' 'altgraph==0.17.5' 'macholib==1.16.4' \
    'packaging==26.3' 'pyinstaller-hooks-contrib==2026.7' 'setuptools==84.0.0'
"$PYTHON" -m PyInstaller --noconfirm --clean --distpath "$BUILD/backend" --workpath "$BUILD/pyinstaller" macos/backend.spec

APP="$DIST/词屿.app"
# Only replace this script's generated staging output, never installed user data.
rm -rf "$APP" "$BUILD/dmg-root"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Helpers" "$APP/Contents/Resources/内容来源" "$BUILD/dmg-root"
cp macos/Info.plist "$APP/Contents/Info.plist"
cp -R "$BUILD/backend/WordIsleBackend.app" "$APP/Contents/Helpers/"
# Keep the arm64 ML component separate; the core remains universal and supports macOS 12.3.
if [ ! -d "$PROJECT/.build/openpronounce/dist/OpenPronounceEngine.app" ]; then
    "$PROJECT/scripts/build_openpronounce.sh"
fi
cp -R "$PROJECT/.build/openpronounce/dist/OpenPronounceEngine.app" "$APP/Contents/Helpers/"
cp macos/安装与使用说明.txt "$APP/Contents/Resources/"
"$PYTHON" - "$APP" <<'PY'
import pathlib, shutil, sys
target = pathlib.Path(sys.argv[1]) / 'Contents/Resources/内容来源'
for source in pathlib.Path('data/sources').rglob('*'):
    if source.is_file() and source.suffix in ('.md', '.txt', '.json', '.tsv'):
        destination = target / source.relative_to('data/sources')
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
shutil.copy2('.build/macos/frameworks/Python.framework/Versions/3.13/lib/python3.13/LICENSE.txt', target / 'Python-LICENSE.txt')
shutil.copy2('.build/macos/python-package/Resources/License.rtf', target / 'Python-Installer-License.rtf')
PY

for arch in arm64 x86_64; do
    swiftc -O -target "$arch-apple-macos12.3" macos/WordIsle.swift -o "$BUILD/WordIsle-$arch" -framework AppKit -framework WebKit
done
lipo -create "$BUILD/WordIsle-arm64" "$BUILD/WordIsle-x86_64" -output "$APP/Contents/MacOS/WordIsle"

# Render the existing favicon's shape using AppKit; no new visual dependency.
cat > "$BUILD/icon.swift" <<'SWIFT'
import AppKit
let image = NSImage(size: NSSize(width: 1024, height: 1024))
image.lockFocus()
let transform = NSAffineTransform(); transform.scale(by: 16); transform.concat()
NSColor(calibratedRed: 0, green: 123/255, blue: 108/255, alpha: 1).setFill()
NSBezierPath(roundedRect: NSRect(x: 0, y: 0, width: 64, height: 64), xRadius: 18, yRadius: 18).fill()
let path = NSBezierPath(); path.lineWidth = 6; path.lineCapStyle = .round; path.lineJoinStyle = .round
path.move(to: NSPoint(x: 12, y: 46))
for (x,y) in [(20,17), (32,37), (44,17), (52,46)] { path.line(to: NSPoint(x:x, y:y)) }
NSColor.white.setStroke(); path.stroke(); image.unlockFocus()
let bitmap = NSBitmapImageRep(data: image.tiffRepresentation!)!
try bitmap.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))
SWIFT
swift "$BUILD/icon.swift" "$BUILD/icon.png"
mkdir -p "$BUILD/AppIcon.iconset"
for size in 16 32 128 256 512; do
    sips -z "$size" "$size" "$BUILD/icon.png" --out "$BUILD/AppIcon.iconset/icon_${size}x${size}.png" >/dev/null
    double=$((size * 2))
    sips -z "$double" "$double" "$BUILD/icon.png" --out "$BUILD/AppIcon.iconset/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$BUILD/AppIcon.iconset" -o "$APP/Contents/Resources/AppIcon.icns"
codesign --force --deep --sign - "$APP"
codesign --force --sign - --entitlements macos/WordIsle.entitlements "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"
cp -R "$APP" "$BUILD/dmg-root/"
cp macos/安装与使用说明.txt "$BUILD/dmg-root/安装与使用说明.txt"
ln -s /Applications "$BUILD/dmg-root/Applications"
DMG="$DIST/词屿-1.4.1-macOS-Universal.dmg"
hdiutil create -volname '词屿 Word Isle' -srcfolder "$BUILD/dmg-root" -ov -format UDZO "$DMG"
hdiutil verify "$DMG"
(cd "$DIST" && shasum -a 256 '词屿-1.4.1-macOS-Universal.dmg' > SHA256SUMS.txt)
echo "Created: $DMG"
