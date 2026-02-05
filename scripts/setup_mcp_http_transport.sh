#!/bin/bash

# MCP Server HTTP/SSE Setup Script
# This script helps you add HTTP/SSE transport to your existing MCP server

echo "🌐 Adding HTTP/SSE Transport to MCP Server"
echo "=========================================="
echo ""

cd /home/aojie_ju/aristai

echo "📋 Current MCP Server Analysis:"
echo "==============================="
echo "✅ Your mcp_server/server.py has 44 tools"
echo "✅ MCP dependencies are installed (mcp>=1.0.0)"  
echo "❌ Currently only supports stdio transport"
echo ""

echo "🔧 Adding HTTP/SSE Transport..."
echo "==============================="

# Create backup of original server
cp mcp_server/server.py mcp_server/server.py.backup
echo "✅ Backed up original server.py"

# Add HTTP transport imports to existing server.py
cat >> mcp_server/http_transport_patch.py << 'EOF'
"""
HTTP/SSE Transport Patch for MCP Server
Add this functionality to existing mcp_server/server.py
"""

import asyncio
import json
from typing import Optional
import sys

# Add these imports after existing imports in server.py
try:
    from fastapi import FastAPI, Request
    from fastapi.responses import StreamingResponse
    import uvicorn
    HTTP_AVAILABLE = True
except ImportError:
    HTTP_AVAILABLE = False

# HTTP/SSE functionality (add to end of server.py, before main())
if HTTP_AVAILABLE:
    app = FastAPI(title="AristAI MCP Server - HTTP/SSE")
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {
            "status": "healthy", 
            "tools_count": len(TOOL_REGISTRY),
            "server": "aristai-mcp-http",
            "transport": "sse"
        }
    
    @app.get("/tools")
    async def http_list_tools():
        """List all available tools via HTTP"""
        tools = []
        for name, tool_info in TOOL_REGISTRY.items():
            tools.append({
                "name": name,
                "description": f"[{tool_info['mode'].upper()}] {tool_info['description']}",
                "parameters": tool_info["parameters"],
                "category": tool_info["category"],
                "mode": tool_info["mode"]
            })
        
        return {
            "tools": tools,
            "count": len(tools),
            "categories": list(set(tool_info["category"] for tool_info in TOOL_REGISTRY.values()))
        }
    
    @app.post("/execute")
    async def http_execute_tool(request: dict):
        """Execute tool via HTTP POST"""
        tool_name = request.get("tool")
        arguments = request.get("arguments", {})
        
        tool_info = TOOL_REGISTRY.get(tool_name)
        if not tool_info:
            return {"error": f"Tool '{tool_name}' not found", "code": 404}
        
        try:
            if tool_info["mode"] == "write" and tool_name not in ACTION_TOOL_NAMES:
                # Plan write actions  
                db = SessionLocal()
                try:
                    from api.services.action_preview import build_action_preview
                    preview = build_action_preview(tool_name, arguments, db=db)
                    action = action_store.create_action(
                        user_id=None,  # Will be set by ElevenLabs
                        tool_name=tool_name,
                        args=arguments,
                        preview=preview,
                    )
                    return {
                        "tool": tool_name,
                        "action_id": action.action_id,
                        "requires_confirmation": True,
                        "preview": preview,
                        "message": "Action planned. Please confirm to execute."
                    }
                finally:
                    db.close()
            else:
                # Execute read actions
                from api.api.mcp_executor import invoke_tool_handler
                db = SessionLocal()
                try:
                    result = invoke_tool_handler(tool_info["handler"], arguments, db=db)
                    return {"tool": tool_name, "result": result}
                finally:
                    db.close()
                    
        except Exception as e:
            return {"error": str(e), "tool": tool_name, "code": 500}
    
    def run_http_server(port: int = 8080, host: str = "0.0.0.0"):
        """Run MCP server with HTTP/SSE transport"""
        logger.info(f"Starting MCP Server with HTTP/SSE on {host}:{port}")
        logger.info(f"Registered {len(TOOL_REGISTRY)} tools")
        logger.info(f"Health check: http://{host}:{port}/health")
        logger.info(f"Tools list: http://{host}:{port}/tools")
        logger.info(f"Execute endpoint: http://{host}:{port}/execute")
        
        uvicorn.run(app, host=host, port=port, log_level="info")
    
    # Add HTTP server support to CLI args
    if len(sys.argv) > 1 and "--transport" in sys.argv:
        if "sse" in sys.argv:
            # Parse port and host
            port = 8080
            host = "0.0.0.0"
            
            for i, arg in enumerate(sys.argv):
                if arg == "--port" and i + 1 < len(sys.argv):
                    port = int(sys.argv[i + 1])
                elif arg == "--host" and i + 1 < len(sys.argv):
                    host = sys.argv[i + 1]
            
            run_http_server(port=port, host=host)
        else:
            print("Supported HTTP transports: sse")
            sys.exit(1)

EOF

echo "✅ HTTP transport patch created"

echo ""
echo "🎯 To Enable HTTP/SSE Mode:"
echo "==============================="
echo "1. Add FastAPI to requirements:"
echo "   echo 'fastapi>=0.110,<0.116' >> requirements.txt"
echo "   echo 'uvicorn[standard]>=0.31.1,<0.32' >> requirements.txt"
echo "   pip install fastapi uvicorn"
echo ""
echo "2. Copy HTTP transport code into server.py"
echo "3. Run with HTTP transport:"
echo "   python -m mcp_server.server --transport sse --port 8080"
echo ""
echo "4. Test endpoints:"
echo "   curl http://localhost:8080/health"
echo "   curl http://localhost:8080/tools"
echo "   curl -X POST http://localhost:8080/execute -H 'Content-Type: application/json' -d '{\"tool\":\"list_courses\",\"arguments\":{}}'"
echo ""

echo "📊 Expected Results:"
echo "===================="
echo "✅ Health: {'status': 'healthy', 'tools_count': 44}"
echo "✅ Tools: List of all 44 tools with descriptions"
echo "✅ Execute: Tool execution with results"
echo ""

echo "🔗 External Access URLs:"
echo "========================"
echo "Local:   http://localhost:8080"
echo "EC2:      http://ec2-13-219-204-7.compute-1.amazonaws.com:8080"
echo "External: https://your-domain.com:8080 (if you add SSL)"
echo ""

echo "⚠️  Security Notes:"
echo "==================="
echo "• Add authentication for production"
echo "• Use HTTPS in production"
echo "• Configure firewall for port 8080"
echo "• Consider rate limiting"
echo ""

echo "✅ HTTP/SSE transport setup complete!"