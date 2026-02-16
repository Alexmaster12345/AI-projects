#!/bin/bash
# Clean up generated screenshots
# This script removes all PNG files from the screenshots directory

set -e

SCREENSHOTS_DIR="$(dirname "$0")/../docs/screenshots"

echo "🧹 Cleaning up screenshots..."
echo "Directory: $SCREENSHOTS_DIR"

if [ -d "$SCREENSHOTS_DIR" ]; then
    # Remove all PNG files except .gitkeep
    find "$SCREENSHOTS_DIR" -name "*.png" -type f -delete
    echo "✅ All PNG files removed"
    echo "📁 Directory structure preserved (.gitkeep remains)"
else
    echo "❌ Screenshots directory not found"
    exit 1
fi

echo ""
echo "💡 To regenerate screenshots, run:"
echo "   ./scripts/setup_screenshots.sh"
echo "   or"
echo "   python scripts/take_screenshots.py"
