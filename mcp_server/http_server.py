#!/usr/bin/env python3
"""
HTTP/SSE MCP Server for AristAI
Run this to expose your MCP server via HTTP/SSE transport
"""

import asyncio
import json
import logging
import os
import sys
from typing import Dict, Any, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# FastAPI imports
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# MCP and existing imports
from mcp.server import Server
from mcp.types import Tool, TextContent, CallToolResult, ListToolsResult
from sqlalchemy.orm import Session

# Your existing imports
from api.core.database import SessionLocal
from api.api.mcp_executor import invoke_tool_handler
from api.services.action_preview import build_action_preview
from api.services.action_store import ActionStore
from api.services.tool_response import normalize_tool_result
from mcp_server.server import TOOL_REGISTRY, ACTION_TOOL_NAMES

# Initialize FastAPI and MCP server
app = FastAPI(
    title="AristAI MCP Server - HTTP/SSE",
    description="HTTP/SSE transport for AristAI MCP tools",
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
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "tools_count": len(TOOL_REGISTRY),
        "server": "aristai-mcp-http",
        "transport": "http/sse",
        "categories": list(set(tool_info["category"] for tool_info in TOOL_REGISTRY.values()))
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
        "categories": list(set(tool_info["category"] for tool_info in TOOL_REGISTRY.values())),
        "server": "aristai-mcp-http"
    }

@app.post("/execute")
async def http_execute_tool(request: dict):
    """Execute tool via HTTP POST - ElevenLabs compatible"""
    tool_name = request.get("tool")
    arguments = request.get("arguments", {})
    user_id = request.get("user_id")  # Optional user ID
    
    logger.info(f"HTTP tool execution request: {tool_name} with args: {arguments}")
    
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
                    "message": "Action planned. Please confirm to execute."
                }
                logger.info(f"Write action planned: {tool_name} -> {action.action_id}")
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
                    "executed": True
                }
                logger.info(f"Tool executed successfully: {tool_name}")
                return result
            finally:
                db.close()
                    
    except Exception as e:
        logger.error(f"Tool execution failed: {tool_name} - {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sse")
async def sse_endpoint():
    """Server-Sent Events endpoint for MCP SSE transport"""
    
    async def event_stream():
        """Generate SSE events for MCP communication"""
        try:
            logger.info("SSE client connected")
            
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'server': 'aristai-mcp-sse'})}\n\n"
            
            # Keep connection alive with periodic pings
            while True:
                await asyncio.sleep(30)  # Ping every 30 seconds
                yield f"data: {json.dumps({'type': 'ping', 'timestamp': asyncio.get_event_loop().time()})}\n\n"
                
        except Exception as e:
            logger.error(f"SSE stream error: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "X-Accel-Buffering": "no"  # Disable buffering for real-time
        }
    )

def run_http_server(port: int = 8080, host: str = "0.0.0.0"):
    """Run MCP server with HTTP/SSE transport"""
    logger.info("=" * 50)
    logger.info("🚀 STARTING ARISTAI MCP SERVER - HTTP/SSE MODE")
    logger.info("=" * 50)
    logger.info(f"📍 Server: http://{host}:{port}")
    logger.info(f"🛠️  Tools: {len(TOOL_REGISTRY)} registered")
    logger.info(f"🏥 Health: http://{host}:{port}/health")
    logger.info(f"📋 Tools: http://{host}:{port}/tools")
    logger.info(f"⚡ Execute: http://{host}:{port}/execute")
    logger.info(f"🌊 SSE: http://{host}:{port}/sse")
    logger.info("=" * 50)
    
    uvicorn.run(
        app, 
        host=host, 
        port=port,
        log_level="info",
        access_log=True
    )

if __name__ == "__main__":
    import os
    
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
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    run_http_server(port=port, host=host)