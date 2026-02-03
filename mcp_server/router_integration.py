"""
Updated API Router with Voice Loop Endpoints.

This file shows how to integrate the voice loop controller
with the existing FastAPI application.

To use: Replace the contents of api/api/router.py with this file,
or merge the voice router inclusion.
"""

from fastapi import APIRouter
from api.api.routes import courses, sessions, posts, polls, reports, users, enrollments, voice
from api.core.config import get_settings

api_router = APIRouter()

# Include all existing route modules
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(courses.router, prefix="/courses", tags=["courses"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(posts.router, prefix="/posts", tags=["posts"])
api_router.include_router(polls.router, prefix="/polls", tags=["polls"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(enrollments.router, prefix="/enrollments", tags=["enrollments"])
api_router.include_router(voice.router, prefix="/voice", tags=["voice"])

# Debug routes only available when DEBUG=true
settings = get_settings()
if settings.debug:
    from api.api.routes import debug
    api_router.include_router(debug.router, prefix="/debug", tags=["debug"])

# ============ Voice Loop Integration ============
# 
# To enable the voice loop HTTP/WebSocket API, add the following:

def include_voice_loop_router(app_router: APIRouter):
    """
    Include voice loop control endpoints.
    
    This adds endpoints for:
    - POST /voice-loop/start - Start the voice loop
    - POST /voice-loop/stop - Stop the voice loop  
    - GET /voice-loop/status - Get voice loop status
    - POST /voice-loop/command - Process a text command
    - WS /voice-loop/ws - WebSocket for real-time voice
    """
    import asyncio
    from typing import Optional, Dict, Any
    from fastapi import WebSocket, WebSocketDisconnect
    from pydantic import BaseModel
    
    voice_loop_router = APIRouter()
    
    # Global controller (in production, would be per-user)
    _controller = None
    
    class VoiceLoopConfig(BaseModel):
        mode: str = "continuous"
        wake_word: str = "hey aristai"
        confirmation_required: bool = True
        user_id: int = 1
    
    class CommandRequest(BaseModel):
        transcript: str
    
    @voice_loop_router.post("/start")
    async def start_voice_loop(config: Optional[VoiceLoopConfig] = None):
        """Start the voice loop."""
        global _controller
        
        from mcp_server.voice_loop import VoiceLoopController, VoiceConfig, VoiceMode
        
        if _controller and _controller._running:
            return {"status": "already_running"}
        
        voice_config = VoiceConfig(
            mode=VoiceMode(config.mode if config else "continuous"),
            wake_word=config.wake_word if config else "hey aristai",
            confirmation_required_for_writes=config.confirmation_required if config else True,
            user_id=config.user_id if config else 1,
        )
        
        _controller = VoiceLoopController(config=voice_config)
        asyncio.create_task(_controller.start())
        
        return {"status": "started", "config": voice_config.__dict__}
    
    @voice_loop_router.post("/stop")
    async def stop_voice_loop():
        """Stop the voice loop."""
        global _controller
        
        if not _controller or not _controller._running:
            return {"status": "not_running"}
        
        await _controller.stop()
        return {"status": "stopped"}
    
    @voice_loop_router.get("/status")
    async def get_voice_loop_status():
        """Get voice loop status."""
        global _controller
        
        if not _controller:
            return {"status": "not_initialized", "running": False}
        
        return _controller.get_status()
    
    @voice_loop_router.post("/command")
    async def process_command(request: CommandRequest):
        """Process a voice command (text input for testing)."""
        from mcp_server.voice_loop import VoiceLoopController
        
        controller = _controller or VoiceLoopController()
        
        try:
            response = await controller._process_command(request.transcript)
            return {
                "transcript": request.transcript,
                "response": response,
                "success": True,
            }
        finally:
            if not _controller:
                controller._close_db()
    
    @voice_loop_router.websocket("/ws")
    async def voice_websocket(websocket: WebSocket):
        """WebSocket for real-time voice interaction."""
        from mcp_server.voice_loop import VoiceLoopController
        from api.services import asr
        import base64
        
        await websocket.accept()
        
        controller = VoiceLoopController(
            on_transcript=lambda t: asyncio.create_task(
                websocket.send_json({"type": "transcript", "data": t})
            ),
            on_response=lambda r: asyncio.create_task(
                websocket.send_json({"type": "response", "data": r})
            ),
        )
        
        try:
            # Send ready message
            await websocket.send_json({"type": "ready", "data": "Voice WebSocket connected"})
            
            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type")
                
                if msg_type == "audio":
                    # Decode and transcribe audio
                    audio_bytes = base64.b64decode(data.get("data", ""))
                    content_type = data.get("content_type", "audio/webm")
                    
                    result = asr.transcribe(audio_bytes, content_type)
                    
                    if result.transcript:
                        await websocket.send_json({
                            "type": "transcript",
                            "data": result.transcript,
                            "language": result.language,
                        })
                        
                        # Process command
                        response = await controller._process_command(result.transcript)
                        await websocket.send_json({
                            "type": "response",
                            "data": response
                        })
                
                elif msg_type == "text":
                    # Direct text input
                    transcript = data.get("data", "")
                    if transcript:
                        response = await controller._process_command(transcript)
                        await websocket.send_json({
                            "type": "response",
                            "data": response
                        })
                
                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                
                elif msg_type == "stop":
                    break
                    
        except WebSocketDisconnect:
            pass
        finally:
            controller._close_db()
    
    app_router.include_router(
        voice_loop_router,
        prefix="/voice-loop",
        tags=["voice-loop"]
    )


# Uncomment the following line to enable voice loop endpoints:
# include_voice_loop_router(api_router)
