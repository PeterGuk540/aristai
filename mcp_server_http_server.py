#!/usr/bin/env python3
"""
Standalone HTTP/SSE MCP Server for AristAI
Exposes your MCP tools via HTTP endpoints for ElevenLabs integration
"""

import asyncio
import json
import logging
import os
import sys
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Direct imports to access your MCP tools
sys.path.insert(0, '.')
from api.core.database import SessionLocal
from api.api.mcp_executor import invoke_tool_handler
from api.services.action_preview import build_action_preview
from api.services.action_store import ActionStore
from api.services.tool_response import normalize_tool_result

# Import your MCP server to get tool registry
try:
    # Import the registry from your existing server
    import importlib.util
    spec = importlib.util.spec_from_file_location("mcp_server", "mcp_server/server.py")
    mcp_module = importlib.util.module_from_spec(spec)
    sys.modules["mcp_server"] = mcp_module
    spec.loader.exec_module(mcp_module)
    TOOL_REGISTRY = mcp_module.TOOL_REGISTRY
    ACTION_TOOL_NAMES = mcp_module.ACTION_TOOL_NAMES
    print(f"✅ Loaded {len(TOOL_REGISTRY)} tools from existing MCP server")
except Exception as e:
    print(f"❌ Failed to load MCP tools: {e}")
    TOOL_REGISTRY = {}
    ACTION_TOOL_NAMES = {}

# Initialize FastAPI
app = FastAPI(
    title="AristAI MCP Server - HTTP/SSE",
    description="HTTP transport for AristAI MCP tools",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger(__name__)
action_store = ActionStore()

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "server": "AristAI MCP Server",
        "transport": "HTTP/SSE",
        "tools_count": len(TOOL_REGISTRY),
        "endpoints": {
            "health": "/health",
            "tools": "/tools", 
            "execute": "/execute",
            "sse": "/sse"
        },
        "elevenlabs_compatible": True
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    categories = list(set(tool_info["category"] for tool_info in TOOL_REGISTRY.values())) if TOOL_REGISTRY else []
    
    return {
        "status": "healthy",
        "tools_count": len(TOOL_REGISTRY),
        "server": "aristai-mcp-http",
        "transport": "http/sse",
        "categories": categories,
        "elevenlabs_ready": True
    }

@app.get("/tools")
async def http_list_tools():
    """List all available tools via HTTP - ElevenLabs compatible"""
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
        "categories": list(set(tool_info["category"] for tool_info in TOOL_REGISTRY.values())),
        "server": "aristai-mcp-http",
        "elevenlabs_webhook_url": "http://ec2-13-219-204-7.compute-1.amazonaws.com:8080/execute"
    }

@app.post("/execute")
async def http_execute_tool(request: dict):
    """Execute tool via HTTP POST - ElevenLabs webhook compatible"""
    tool_name = request.get("tool")
    arguments = request.get("arguments", {})
    user_id = request.get("user_id")  # Optional user ID
    
    logger.info(f"🔧 HTTP tool execution: {tool_name} with args: {arguments}")
    
    tool_info = TOOL_REGISTRY.get(tool_name)
    if not tool_info:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    
    try:
        if tool_info["mode"] == "write" and tool_name not in ACTION_TOOL_NAMES:
            # Plan write actions
            db = SessionLocal()
            try:
                preview = build_action_preview(tool_name, arguments, db=db)
                action = action_store.create_action(
                    user_id=user_id,
                    tool_name=tool_name,
                    args=arguments,
                    preview=preview,
                )
                result = {
                    "tool": tool_name,
                    "success": True,
                    "action_id": action.action_id,
                    "requires_confirmation": True,
                    "preview": preview,
                    "message": "Action planned. Please confirm to execute.",
                    "elevenlabs_response": True
                }
                logger.info(f"✅ Write action planned: {tool_name} -> {action.action_id}")
                return result
            finally:
                db.close()
        else:
            # Execute read actions directly
            db = SessionLocal()
            try:
                handler_result = invoke_tool_handler(tool_info["handler"], arguments, db=db)
                normalized_result = normalize_tool_result(handler_result, tool_name)
                
                result = {
                    "tool": tool_name,
                    "success": normalized_result.get("ok", True),
                    "result": normalized_result,
                    "executed": True,
                    "elevenlabs_response": True
                }
                logger.info(f"✅ Tool executed: {tool_name}")
                return result
            finally:
                db.close()
                    
    except Exception as e:
        logger.error(f"❌ Tool execution failed: {tool_name} - {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sse")
async def sse_endpoint():
    """Server-Sent Events endpoint for MCP SSE transport"""
    
    async def event_stream():
        """Generate SSE events for MCP communication"""
        try:
            logger.info("🌊 SSE client connected")
            
            # Send initial connection event
            init_data = {
                'type': 'connected', 
                'server': 'aristai-mcp-sse',
                'tools_count': len(TOOL_REGISTRY),
                'timestamp': asyncio.get_event_loop().time()
            }
            yield f"data: {json.dumps(init_data)}\n\n"
            
            # Keep connection alive with periodic pings
            while True:
                await asyncio.sleep(30)  # Ping every 30 seconds
                ping_data = {
                    'type': 'ping', 
                    'timestamp': asyncio.get_event_loop().time(),
                    'server': 'aristai-mcp-sse'
                }
                yield f"data: {json.dumps(ping_data)}\n\n"
                
        except Exception as e:
            logger.error(f"SSE stream error: {str(e)}")
            error_data = {
                'type': 'error', 
                'message': str(e),
                'timestamp': asyncio.get_event_loop().time()
            }
            yield f"data: {json.dumps(error_data)}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "X-Accel-Buffering": "no"
        }
    )

def run_http_server(port: int = 8080, host: str = "0.0.0.0"):
    """Run MCP server with HTTP/SSE transport"""
    
    print("=" * 60)
    print("🚀 ARISTAI MCP SERVER - HTTP/SSE MODE")
    print("=" * 60)
    print(f"📍 Server: http://{host}:{port}")
    print(f"🛠️  Tools: {len(TOOL_REGISTRY)} registered")
    print(f"🏥 Health: http://{host}:{port}/health")
    print(f"📋 Tools: http://{host}:{port}/tools")
    print(f"⚡ Execute: http://{host}:{port}/execute")
    print(f"🌊 SSE: http://{host}:{port}/sse")
    print("=" * 60)
    print("🎯 Ready for ElevenLabs integration!")
    print("📝 ElevenLabs Webhook URL: http://ec2-13-219-204-7.compute-1.amazonaws.com:8080/execute")
    print("=" * 60)
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info(f"Starting HTTP MCP server on {host}:{port}")
    logger.info(f"Registered {len(TOOL_REGISTRY)} tools")
    
    uvicorn.run(
        app, 
        host=host, 
        port=port,
        log_level="info",
        access_log=True
    )

if __name__ == "__main__":
    # Parse command line arguments
    port = 8080
    host = "0.0.0.0"
    
    if "--port" in sys.argv:
        port_idx = sys.argv.index("--port") + 1
        if port_idx < len(sys.argv):
            port = int(sys.argv[port_idx])
    
    if "--host" in sys.argv:
        host_idx = sys.argv.index("--host") + 1
        if host_idx < len(sys.argv):
            host = sys.argv[host_idx]
    
    run_http_server(port=port, host=host)