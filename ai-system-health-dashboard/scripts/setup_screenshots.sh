#!/bin/bash
# Setup script for screenshot capture
# This script helps set up the environment for taking screenshots

set -e

echo "🖼️  ASHD Screenshot Setup"
echo "=========================="

# Check if Chrome/Chromium is installed
if ! command -v google-chrome &> /dev/null && ! command -v chromium &> /dev/null && ! command -v chromium-browser &> /dev/null; then
    echo "❌ Chrome/Chromium not found. Please install it first:"
    echo "   Ubuntu/Debian: sudo apt-get install chromium-browser"
    echo "   CentOS/RHEL:   sudo yum install chromium"
    echo "   macOS:        brew install --cask google-chrome"
    exit 1
fi

echo "✅ Chrome/Chromium found"

# Check if Python dependencies are installed
echo "📦 Checking Python dependencies..."
python3 -c "import selenium, PIL, requests" 2>/dev/null || {
    echo "❌ Missing Python dependencies. Installing..."
    pip install selenium pillow requests
}

echo "✅ Python dependencies installed"

# Check if server is running
echo "🔗 Checking if ASHD server is running..."
if curl -s http://localhost:8000/ > /dev/null; then
    echo "✅ ASHD server is running"
else
    echo "❌ ASHD server is not running on http://localhost:8000"
    echo "   Please start it with: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
    exit 1
fi

# Set up environment variables
echo ""
echo "🔧 Setting up environment variables..."
export ASHD_URL="http://localhost:8000"
export ASHD_USER="admin"
export ASHD_PASS="admin123"

echo "✅ Environment variables set:"
echo "   ASHD_URL=$ASHD_URL"
echo "   ASHD_USER=$ASHD_USER"
echo "   ASHD_PASS=$ASHD_PASS"

# Take screenshots
echo ""
echo "📸 Taking screenshots..."
cd "$(dirname "$0")/.."
python3 scripts/take_screenshots.py

echo ""
echo "🎉 Screenshots captured successfully!"
echo "📁 Location: docs/screenshots/"
echo "🌐 View them: Open docs/index.html in your browser"
