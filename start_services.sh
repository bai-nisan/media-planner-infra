#!/bin/bash

# Start Services Script for Media Planner Infrastructure
# This script starts both FastAPI and LangGraph services

echo "🚀 Starting Media Planner Services..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run 'python -m venv venv' first."
    exit 1
fi

# Activate virtual environment
echo "📦 Activating virtual environment..."
source venv/bin/activate

# Function to start FastAPI service
start_fastapi() {
    echo "🔧 Starting FastAPI Auth Service on port 8000..."
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
    FASTAPI_PID=$!
    echo "FastAPI started with PID: $FASTAPI_PID"
}

# Function to start LangGraph service
start_langgraph() {
    echo "🧠 Starting LangGraph Dev Server on port 8123..."
    langgraph dev --host 0.0.0.0 --port 8123 &
    LANGGRAPH_PID=$!
    echo "LangGraph started with PID: $LANGGRAPH_PID"
}

# Start services
start_fastapi
sleep 3  # Wait for FastAPI to start
start_langgraph

echo ""
echo "✅ Services started successfully!"
echo "📚 FastAPI Docs: http://localhost:8000/api/docs"
echo "🎨 LangGraph Studio: https://smith.langchain.com/studio/?baseUrl=http://localhost:8123"
echo "🔍 Health Check: http://localhost:8000/health"
echo ""
echo "Press Ctrl+C to stop all services..."

# Wait for interrupt
trap 'echo "🛑 Stopping services..."; kill $FASTAPI_PID $LANGGRAPH_PID 2>/dev/null; exit' INT
wait 