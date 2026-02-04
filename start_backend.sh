#!/bin/bash
echo '🚀 Starting AristAI backend server...'
echo '📍 Backend will run on http://localhost:8000'
echo '📚 API docs: http://localhost:8000/docs'
echo ''
echo 'Press Ctrl+C to stop the server'
echo '========================='

# Activate virtual environment
source venv/bin/activate

# Start the FastAPI server
cd api && uvicorn main:app --host 0.0.0.0 --port 8000 --reload
