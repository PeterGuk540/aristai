"""
HTTP/SSE Transport for MCP Server
Add this to mcp_server/server.py to enable external HTTP access
"""

import asyncio
import json
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import uvicorn

# Add these imports to your existing server.py
from mcp.types import CallToolRequest, ListToolsRequest
from mcp.server.sse import SseServerTransport
from mcp.server import Server

# Initialize FastAPI app for HTTP transport
app = FastAPI(title="AristAI MCP Server - HTTP/SSE")
mcp_server = Server("aristai-mcp-server-http")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "tools_count": len(TOOL_REGISTRY),
        "server": "aristai-mcp-http"
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
async def http_execute_tool(request: CallToolRequest):
    """Execute tool via HTTP POST"""
    tool_name = request.params.name
    arguments = request.params.arguments or {}
    
    tool_info = TOOL_REGISTRY.get(tool_name)
    if not tool_info:
        return {"error": f"Tool '{tool_name}' not found", "code": 404}
    
    try:
        if tool_info["mode"] == "write" and tool_name not in ACTION_TOOL_NAMES:
            # Plan write actions
            db = SessionLocal()
            try:
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
            # Execute read actions or confirmed actions
            db = SessionLocal()
            try:
                result = invoke_tool_handler(tool_info["handler"], arguments, db=db)
                return {"tool": tool_name, "result": result}
            finally:
                db.close()
                
    except Exception as e:
        return {"error": str(e), "tool": tool_name, "code": 500}

@app.get("/sse")
async def sse_endpoint():
    """Server-Sent Events endpoint for MCP SSE transport"""
    
    async def event_stream():
        """Generate SSE events for MCP communication"""
        try:
            # Create SSE transport
            transport = SseServerTransport("/sse")
            
            # Initialize server with SSE transport
            await mcp_server.run(
                read_stream=transport.read_stream,
                write_stream=transport.write_stream,
                create_initialization_options=mcp_server.create_initialization_options()
            )
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*"
        }
    )

# CLI support for HTTP mode
def run_http_server(port: int = 8080, host: str = "0.0.0.0"):
    """Run MCP server with HTTP/SSE transport"""
    logger.info(f"Starting MCP Server with HTTP/SSE on {host}:{port}")
    logger.info(f"Registered {len(TOOL_REGISTRY)} tools")
    logger.info(f"Health check: http://{host}:{port}/health")
    logger.info(f"Tools list: http://{host}:{port}/tools")
    logger.info(f"SSE endpoint: http://{host}:{port}/sse")
    
    uvicorn.run(
        app, 
        host=host, 
        port=port,
        log_level="info"
    )

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and "--transport" in sys.argv:
        if "--transport" in sys.argv and "sse" in sys.argv:
            # Parse port from command line
            port = 8080
            host = "0.0.0.0"
            
            for i, arg in enumerate(sys.argv):
                if arg == "--port" and i + 1 < len(sys.argv):
                    port = int(sys.argv[i + 1])
                elif arg == "--host" and i + 1 < len(sys.argv):
                    host = sys.argv[i + 1]
            
            run_http_server(port=port, host=host)
        else:
            print("Supported transports: sse")
            sys.exit(1)
    else:
        # Default: run stdio server
        asyncio.run(main())