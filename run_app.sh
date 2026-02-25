#!/bin/bash

# TCG Tracker - Flask Web App Runner
# This script starts the Flask development server for local editing

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "🎮 TCG Tracker - Starting Web Application..."
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
echo "✅ Starting Flask server..."
echo "   🌐 Open your browser to: http://127.0.0.1:5001"
echo "   📝 You can now add/edit transactions through the web interface"
echo "   ⛔ Press Ctrl+C to stop"
echo ""

python3 app.py
