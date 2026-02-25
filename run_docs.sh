#!/bin/bash

# TCG Tracker - Local GitHub Pages Preview
# This script rebuilds docs/ data and serves the static site locally.

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "🧪 TCG Tracker - Local GitHub Pages Preview"
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "⚠️  Virtual environment not found. Creating one..."
    python3 -m venv .venv
    source .venv/bin/activate
    echo "✓ Installing dependencies..."
    pip install -r requirements.txt
else
    echo "✓ Activating virtual environment..."
    source .venv/bin/activate
fi

echo ""
echo "✓ Rebuilding docs/data..."
python daily_run.py --docs-only

echo ""
echo "✅ Starting local static server for docs/"
echo "   🌐 Open: http://127.0.0.1:8000/index.html"
echo "   ⛔ Press Ctrl+C to stop"
echo ""

cd "$SCRIPT_DIR/docs"
python -m http.server 8000
