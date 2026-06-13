#!/bin/bash

# H2Open Quick Start Script
# Starts both backend and frontend in separate terminal windows

echo "🚀 Starting H2Open System..."
echo ""

# Check if we're in the right directory
if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo "❌ Error: Must run from h2open-project directory"
    echo "Current directory: $(pwd)"
    exit 1
fi

# Function to check if port is in use
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        return 0
    else
        return 1
    fi
}

# Check if backend is already running
if check_port 8000; then
    echo "⚠️  Backend already running on port 8000"
else
    echo "📡 Starting backend..."
    osascript -e 'tell application "Terminal" to do script "cd \"'"$(pwd)"'/backend\" && source venv/bin/activate && python main.py"'
    sleep 2
fi

# Check if frontend is already running
if check_port 5173; then
    echo "⚠️  Frontend already running on port 5173"
else
    echo "🌐 Starting frontend..."
    osascript -e 'tell application "Terminal" to do script "cd \"'"$(pwd)"'/frontend\" && npm run dev"'
    sleep 2
fi

echo ""
echo "✅ H2Open is starting!"
echo ""
echo "📍 URLs:"
echo "   Frontend: http://localhost:5173"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "💡 Tip: Press Ctrl+C in each terminal to stop services"
