#!/bin/bash
# Picture Overview Program - Quick Start Script
# This script sets up and runs the screenshot capture tool

set -e

echo "🖼️  ABTPi18n Picture Overview Program"
echo "======================================="
echo ""

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 18+ first."
    exit 1
fi

# Check Node.js version
NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "❌ Node.js version 18 or higher is required. Current version: $(node -v)"
    exit 1
fi

echo "✅ Node.js version: $(node -v)"
echo ""

# Navigate to tools directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if package.json exists
if [ ! -f "package.json" ]; then
    echo "❌ package.json not found in tools directory"
    exit 1
fi

# Install dependencies if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
    echo ""
fi

# Check if Playwright is installed
if [ ! -d "node_modules/playwright" ]; then
    echo "❌ Playwright not found. Installing..."
    npm install playwright
    echo ""
fi

# Install Playwright browsers if needed
echo "🔧 Checking Playwright browsers..."
if ! npx playwright install chromium --dry-run &> /dev/null; then
    echo "📥 Installing Playwright Chromium browser..."
    npx playwright install chromium
    echo ""
fi

# Check if frontend is running
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
echo "🔍 Checking if frontend is accessible at $FRONTEND_URL..."

if command -v curl &> /dev/null; then
    if curl -s --head --connect-timeout 5 "$FRONTEND_URL" > /dev/null; then
        echo "✅ Frontend is accessible"
    else
        echo "⚠️  Warning: Frontend may not be running at $FRONTEND_URL"
        echo "   Make sure to start the frontend before running screenshots:"
        echo "   cd apps/frontend && npm run dev"
        echo ""
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
else
    echo "⚠️  curl not found, skipping frontend check"
fi

echo ""
echo "🚀 Starting screenshot capture..."
echo "   Base URL: $FRONTEND_URL"
echo "   Output: ./screenshots/"
echo ""

# Run the screenshot tool
node screenshot_pages.js

# Check if screenshots were generated
if [ -f "screenshots/index.html" ]; then
    echo ""
    echo "✨ Screenshot capture complete!"
    echo ""
    echo "📁 Screenshots saved to: ./screenshots/"
    echo "🌐 View results: open ./screenshots/index.html"
    echo ""
    
    # Try to open the index.html in default browser
    if command -v xdg-open &> /dev/null; then
        read -p "Open viewer in browser? (Y/n) " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            xdg-open "screenshots/index.html"
        fi
    elif command -v open &> /dev/null; then
        read -p "Open viewer in browser? (Y/n) " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            open "screenshots/index.html"
        fi
    fi
else
    echo ""
    echo "⚠️  Warning: index.html was not generated"
    echo "   Check the logs above for errors"
    exit 1
fi
