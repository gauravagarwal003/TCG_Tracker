#!/bin/bash

# Pokemon Tracker - Local Development Server

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "🎮 Pokemon Tracker - Starting local server..."
echo ""

# Activate virtual environment
if [ -d ".venv" ]; then
    echo "✓ Activating virtual environment..."
    source .venv/bin/activate
else
    echo "⚠️  Virtual environment not found. Creating one..."
    python3 -m venv .venv
    source .venv/bin/activate
    echo "✓ Installing dependencies..."
    pip install -r requirements.txt
fi

# Build the site
echo "✓ Building site..."
python build_site.py

# Start the server
echo ""
echo "✅ Starting server at http://localhost:8000"
echo "   Press Ctrl+C to stop"
echo ""

cd docs
python -m http.server 8000
