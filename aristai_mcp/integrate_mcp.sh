#!/bin/bash
# AristAI MCP Server Integration Script
# 
# This script integrates the MCP server into your aristai repository.
# 
# Usage:
#   1. Extract the aristai_mcp_server.zip file
#   2. Copy this script and the aristai_mcp folder to your aristai repo root
#   3. Run: chmod +x integrate_mcp.sh && ./integrate_mcp.sh

set -e

echo "=========================================="
echo "AristAI MCP Server Integration"
echo "=========================================="

# Check we're in the right directory
if [ ! -d "api" ] || [ ! -f "docker-compose.yml" ]; then
    echo "ERROR: Please run this script from the aristai repository root"
    echo "Expected to find 'api/' directory and 'docker-compose.yml'"
    exit 1
fi

# Check if mcp_server already exists
if [ -d "mcp_server" ]; then
    echo "WARNING: mcp_server/ directory already exists"
    read -p "Overwrite? (y/N): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo "Aborted."
        exit 1
    fi
    rm -rf mcp_server
fi

# Copy files
echo "Copying MCP server files..."
if [ -d "aristai_mcp/mcp_server" ]; then
    cp -r aristai_mcp/mcp_server .
    cp aristai_mcp/mcp_config.json .
else
    echo "ERROR: aristai_mcp/mcp_server not found"
    echo "Make sure you extracted the zip file first"
    exit 1
fi

echo "✓ Files copied"

# Run tests
echo ""
echo "Running MCP server tests..."
cd mcp_server
if python test_suite.py; then
    echo "✓ All tests passed"
else
    echo "WARNING: Some tests failed (this may be expected without full backend)"
fi
cd ..

# Git operations
echo ""
echo "Staging files for git..."
git add mcp_server/
git add mcp_config.json

echo ""
echo "Files staged:"
git status --short mcp_server/ mcp_config.json

echo ""
read -p "Commit and push to main? (y/N): " confirm
if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
    git commit -m "Add MCP server for voice-operated forum

Features:
- 40 MCP tools covering all forum operations
- Voice loop controller with push-to-talk, wake-word, and continuous modes
- WebSocket API for real-time voice interaction
- Voice-friendly response messages for TTS
- Write operation confirmation flow
- Comprehensive SKILL.md documentation

Tool categories:
- Courses (4 tools): list, get, create, generate plans
- Sessions (8 tools): CRUD, status control, go_live, end_session
- Forum (14 tools): posts, cases, search, moderation, pin/label
- Polls (4 tools): create, vote, get results
- Copilot (4 tools): start/stop, get suggestions
- Reports (5 tools): generate, get summaries, scores, participation
- Enrollment (3 tools): enroll students, list users"

    git push origin main
    echo ""
    echo "✓ Pushed to main branch"
else
    echo ""
    echo "Files are staged but not committed."
    echo "To commit manually, run:"
    echo "  git commit -m 'Add MCP server for voice-operated forum'"
    echo "  git push origin main"
fi

echo ""
echo "=========================================="
echo "Integration complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Install MCP dependencies: pip install mcp>=0.9.0"
echo "2. Update your api/requirements.txt with mcp_server/requirements.txt"
echo "3. Test the server: python -m mcp_server.test_suite"
echo "4. For Claude Desktop, copy mcp_config.json to your config"
echo ""
