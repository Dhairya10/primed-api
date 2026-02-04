#!/bin/bash

# PM Interview Prep - Development Server Startup Script

set -e

echo "🚀 Starting Prep API..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found!"
    echo "📝 Create .env file with your Supabase credentials"
    echo "   Copy .env.example to .env and fill in your values"
    exit 1
fi

# Deactivate conda if active
if [ ! -z "$CONDA_DEFAULT_ENV" ]; then
    echo "⚠️  Conda environment detected, deactivating..."
    # Note: This warning is shown but conda deactivate must be run by user
    echo "   Please run: conda deactivate && conda deactivate"
    echo "   Then run this script again"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d .venv ]; then
    echo "📦 Creating virtual environment..."
    uv venv
fi

# Install/update dependencies
echo "📦 Installing dependencies..."
uv sync

# Run the application using project's Python directly
echo "✅ Starting FastAPI server..."
echo "📍 API will be available at: http://localhost:8000"
echo "📖 API docs available at: http://localhost:8000/docs"
echo ""

# Use absolute path to project's Python
# --log-level info: Show INFO level logs (includes our logger.info() messages)
# --reload: Auto-reload on code changes (development only)
# --host 0.0.0.0: Listen on all interfaces
# --port 8000: Default port
.venv/bin/python -m uvicorn src.prep.main:app --reload --host 0.0.0.0 --port 8000 --log-level info
