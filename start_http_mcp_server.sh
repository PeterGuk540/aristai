#!/bin/bash

# Quick Start HTTP MCP Server
echo "🚀 Starting HTTP MCP Server for ElevenLabs Integration"
echo "======================================================"
echo ""

cd /home/aojie_ju/aristai

# Install HTTP dependencies if needed
echo "📦 Installing HTTP dependencies..."
pip install fastapi uvicorn --quiet

echo "✅ Dependencies installed"
echo ""

# Start HTTP MCP server
echo "🌐 Starting HTTP MCP server on port 8080..."
echo "🔗 ElevenLabs Webhook: http://ec2-13-219-204-7.compute-1.amazonaws.com:8080/execute"
echo ""

python3 mcp_server_http_server.py --port 8080 --host 0.0.0.0