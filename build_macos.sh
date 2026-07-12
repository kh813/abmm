#!/bin/bash
set -e

echo "=== ABMM macOS Build Script (arm64) ==="

# 1. 仮想環境のアクティベート
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
else
    echo "Error: .venv virtual environment not found. Please set up the environment first."
    exit 1
fi

# 2. クリーンアップ
echo "Cleaning up previous build directories..."
rm -rf build dist

# 3. PyInstaller によるビルドの実行
echo "Running PyInstaller..."
pyinstaller --clean abmm.spec

# 4. アドホック署名の付与
echo "Applying ad-hoc code signature to ABMM.app..."
if [ -d "dist/ABMM.app" ]; then
    codesign --force --deep --sign - dist/ABMM.app
    echo "Ad-hoc signing completed successfully."
else
    echo "Error: dist/ABMM.app was not created."
    exit 1
fi

# 5. 配布用 ZIP アーカイブの作成 (ditto を使用)
echo "Creating ZIP distribution archive..."
ditto -c -k --sequesterRsrc dist/ABMM.app dist/ABMM-macos-arm64.zip
echo "Created: dist/ABMM-macos-arm64.zip"

echo "=== Build finished successfully! ==="
