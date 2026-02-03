"""
Voice Loop Controller for AristAI.

This module implements a continuous voice interaction loop that:
1. Listens for voice input (via ASR)
2. Processes the command using Claude/LLM
3. Executes the appropriate MCP tools
4. Speaks the response back (via TTS)
5. Repeats

Supports multiple modes:
- Push-to-talk: Activated by a button press
- Wake-word: Activated by saying "Hey AristAI"
- Continuous: Always listening (with silence detection)

Integration options:
- Standalone: Uses local microphone and speakers
- LiveKit: Connects to a LiveKit room for remote audio
- WebSocket: Connects to a browser-based interface
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from api.core.config import get_settings
from api.services import asr, tts

logger = logging.getLogger(__name__)


class VoiceMode(str, Enum):
    """Voice activation mode."""
    PUSH_TO_TALK = "push_to_talk"
    WAKE_WORD = "wake_word"
    CONTINUOUS = "continuous"


class VoiceState(str, Enum):
    """Current state of the voice loop."""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"


@dataclass
class VoiceConfig:
    """Configuration for the voice loop."""
    mode: VoiceMode = VoiceMode.CONTINUOUS
    wake_word: str = "hey aristai"
    silence_threshold_seconds: float = 1.5
    max_listen_seconds: float = 30.0
    auto_listen_after_response: bool = True
    confirmation_required_for_writes: bool = True
    speak_confirmations: bool = True
    user_id: int = 1  # Default instructor user ID
    
    # Audio settings
    sample_rate: int = 16000
    channels: int = 1


@dataclass
class VoiceContext:
    """Context maintained across voice interactions."""
    current_course_id: Optional[int] = None
    current_session_id: Optional[int] = None
    last_tool_results: List[Dict[str, Any]] = field(default_factory=list)
    pending_confirmations: List[Dict[str, Any]] = field(default_factory=list)
    conversation_history: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class VoiceLoopStats:
    """Statistics for the voice loop session."""
    start_time: float = 0.0
    total_interactions: int = 0
    successful_commands: int = 0
    failed_commands: int = 0
    total_tokens_used: int = 0
    total_audio_seconds: float = 0.0


class VoiceLoopController:
    """
    Main controller for continuous voice interaction.
    
    This class orchestrates the listen -> process -> speak loop
    and manages context across interactions.
    """
    
    def __init__(
        self,
        config: Optional[VoiceConfig] = None,
        on_state_change: Optional[Callable[[VoiceState], None]] = None,
        on_transcript: Optional[Callable[[str], None]] = None,
        on_response: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize the voice loop controller.
        
        Args:
            config: Voice configuration options
            on_state_change: Callback when state changes
            on_transcript: Callback when transcript is received
            on_response: Callback when response is generated
        """
        self.config = config or VoiceConfig()
        self.context = VoiceContext()
        self.stats = VoiceLoopStats()
        self.state = VoiceState.IDLE
        self._running = False
        self._stop_event = asyncio.Event()
        
        # Callbacks
        self._on_state_change = on_state_change
        self._on_transcript = on_transcript
        self._on_response = on_response
        
        # Database session (lazy loaded)
        self._db = None
    
    def _set_state(self, new_state: VoiceState):
        """Update state and trigger callback."""
        self.state = new_state
        if self._on_state_change:
            self._on_state_change(new_state)
        logger.debug(f"Voice state: {new_state.value}")
    
    def _get_db(self):
        """Get or create database session."""
        if self._db is None:
            from api.core.database import SessionLocal
            self._db = SessionLocal()
        return self._db
    
    def _close_db(self):
        """Close database session."""
        if self._db:
            self._db.close()
            self._db = None
    
    async def start(self):
        """Start the voice loop."""
        if self._running:
            logger.warning("Voice loop already running")
            return
        
        self._running = True
        self._stop_event.clear()
        self.stats.start_time = time.time()
        
        logger.info(f"Starting voice loop in {self.config.mode.value} mode")
        
        # Speak welcome message
        await self._speak("AristAI voice assistant ready. How can I help you?")
        
        try:
            while self._running and not self._stop_event.is_set():
                await self._run_iteration()
        except Exception as e:
            logger.exception(f"Voice loop error: {e}")
            self._set_state(VoiceState.ERROR)
        finally:
            self._close_db()
            self._running = False
            logger.info("Voice loop stopped")
    
    async def stop(self):
        """Stop the voice loop."""
        logger.info("Stopping voice loop...")
        self._running = False
        self._stop_event.set()
    
    async def _run_iteration(self):
        """Run a single listen -> process -> speak iteration."""
        # Check for pending confirmations first
        if self.context.pending_confirmations:
            await self._handle_pending_confirmations()
            return
        
        # Listen for input
        self._set_state(VoiceState.LISTENING)
        transcript = await self._listen()
        
        if not transcript:
            # No input received, continue loop
            await asyncio.sleep(0.1)
            return
        
        # Check for stop command
        if self._is_stop_command(transcript):
            await self._speak("Goodbye!")
            await self.stop()
            return
        
        # Trigger callback
        if self._on_transcript:
            self._on_transcript(transcript)
        
        # Process the command
        self._set_state(VoiceState.PROCESSING)
        response = await self._process_command(transcript)
        
        # Speak the response
        self._set_state(VoiceState.SPEAKING)
        await self._speak(response)
        
        # Update stats
        self.stats.total_interactions += 1
        
        # Return to idle (or listening if continuous)
        if self.config.auto_listen_after_response:
            # Small pause before next listen
            await asyncio.sleep(0.5)
        else:
            self._set_state(VoiceState.IDLE)
    
    async def _listen(self) -> Optional[str]:
        """
        Listen for voice input and return transcript.
        
        Returns:
            Transcript string or None if no input
        """
        # For now, this is a placeholder that would be replaced with
        # actual audio capture from microphone or voicemode integration
        
        # In a real implementation, this would:
        # 1. Capture audio from microphone
        # 2. Detect speech/silence
        # 3. Send to ASR service
        # 4. Return transcript
        
        # For testing, we can simulate with input
        # In production, this would integrate with voicemode MCP server
        
        logger.debug("Listening for voice input...")
        
        # Placeholder: would be replaced with actual audio capture
        # For now, simulate with a small delay
        await asyncio.sleep(0.1)
        
        return None  # No input in this placeholder
    
    async def _process_command(self, transcript: str) -> str:
        """
        Process a voice command and return the response.
        
        Args:
            transcript: The transcribed voice input
            
        Returns:
            Response text to speak back
        """
        logger.info(f"Processing command: {transcript}")
        
        try:
            # Use the voice orchestrator to create a plan
            from workflows.voice_orchestrator import run_voice_orchestrator
            result = run_voice_orchestrator(transcript)
            
            if result.get("error"):
                return f"Sorry, I couldn't understand that. {result['error']}"
            
            plan = result.get("plan", {})
            steps = plan.get("steps", [])
            
            if not steps:
                return "I understood you, but I'm not sure what action to take. Could you rephrase?"
            
            # Check for write operations that need confirmation
            write_steps = [s for s in steps if s.get("mode") == "write"]
            
            if write_steps and self.config.confirmation_required_for_writes:
                # Store for confirmation
                self.context.pending_confirmations = write_steps
                
                # Describe what will happen
                tool_names = [s["tool_name"] for s in write_steps]
                return f"I'll need to {plan.get('intent', 'perform an action')}. This will: {', '.join(tool_names)}. Should I proceed? Say yes or no."
            
            # Execute the plan
            return await self._execute_plan(steps)
            
        except Exception as e:
            logger.exception(f"Command processing error: {e}")
            self.stats.failed_commands += 1
            return f"Sorry, something went wrong: {str(e)}"
    
    async def _execute_plan(self, steps: List[Dict[str, Any]]) -> str:
        """
        Execute a plan's steps and return a summary.
        
        Args:
            steps: List of tool steps to execute
            
        Returns:
            Summary of execution results
        """
        from mcp_server.server import TOOL_REGISTRY
        
        db = self._get_db()
        results = []
        
        for step in steps:
            tool_name = step.get("tool_name")
            args = step.get("args", {})
            
            if tool_name not in TOOL_REGISTRY:
                results.append({
                    "tool": tool_name,
                    "success": False,
                    "error": f"Unknown tool: {tool_name}"
                })
                continue
            
            tool_info = TOOL_REGISTRY[tool_name]
            handler = tool_info["handler"]
            
            try:
                result = handler(db, **args)
                results.append({
                    "tool": tool_name,
                    "success": "error" not in result,
                    "result": result
                })
                
                # Update context based on results
                self._update_context(tool_name, result)
                
            except Exception as e:
                logger.exception(f"Tool execution error: {tool_name}")
                results.append({
                    "tool": tool_name,
                    "success": False,
                    "error": str(e)
                })
        
        # Store results in context
        self.context.last_tool_results = results
        
        # Generate summary
        return self._summarize_results(results)
    
    def _update_context(self, tool_name: str, result: Dict[str, Any]):
        """Update context based on tool execution results."""
        # Track current course/session for follow-up commands
        if "course_id" in result:
            self.context.current_course_id = result["course_id"]
        if "session_id" in result:
            self.context.current_session_id = result["session_id"]
    
    def _summarize_results(self, results: List[Dict[str, Any]]) -> str:
        """Generate a voice-friendly summary of execution results."""
        if not results:
            return "No actions were taken."
        
        # Check if all succeeded
        all_success = all(r.get("success", False) for r in results)
        
        if all_success:
            self.stats.successful_commands += 1
            
            # Use the message from the last result if available
            last_result = results[-1].get("result", {})
            if isinstance(last_result, dict) and "message" in last_result:
                return last_result["message"]
            
            return f"Done. Completed {len(results)} action{'s' if len(results) > 1 else ''}."
        else:
            self.stats.failed_commands += 1
            
            # Describe what failed
            failed = [r for r in results if not r.get("success", False)]
            return f"Some actions failed. {failed[0].get('error', 'Unknown error')}"
    
    async def _handle_pending_confirmations(self):
        """Handle pending write operations that need confirmation."""
        if not self.context.pending_confirmations:
            return
        
        self._set_state(VoiceState.LISTENING)
        transcript = await self._listen()
        
        if not transcript:
            return
        
        transcript_lower = transcript.lower().strip()
        
        if transcript_lower in ["yes", "yeah", "yep", "sure", "proceed", "do it", "confirm"]:
            # Execute the pending writes
            self._set_state(VoiceState.PROCESSING)
            response = await self._execute_plan(self.context.pending_confirmations)
            self.context.pending_confirmations = []
            
            self._set_state(VoiceState.SPEAKING)
            await self._speak(response)
            
        elif transcript_lower in ["no", "nope", "cancel", "stop", "nevermind"]:
            self.context.pending_confirmations = []
            await self._speak("Cancelled. What else can I help with?")
            
        else:
            # Didn't understand, ask again
            await self._speak("Please say yes to proceed or no to cancel.")
    
    async def _speak(self, text: str):
        """
        Speak text using TTS.
        
        Args:
            text: Text to speak
        """
        logger.info(f"Speaking: {text[:100]}...")
        
        # Trigger callback
        if self._on_response:
            self._on_response(text)
        
        # Use TTS service
        try:
            result = tts.synthesize(text)
            
            # In a real implementation, this would play the audio
            # For now, just log it
            if result.audio_bytes:
                logger.debug(f"TTS generated {len(result.audio_bytes)} bytes of audio")
            
            # Simulate speaking time (rough estimate: 150 words/minute)
            word_count = len(text.split())
            speak_time = word_count / 150 * 60
            await asyncio.sleep(min(speak_time, 5.0))  # Cap at 5 seconds
            
        except Exception as e:
            logger.error(f"TTS error: {e}")
    
    def _is_stop_command(self, transcript: str) -> bool:
        """Check if the transcript is a stop command."""
        stop_phrases = [
            "stop listening",
            "goodbye",
            "exit",
            "quit",
            "bye",
            "stop voice",
            "end session",
        ]
        transcript_lower = transcript.lower().strip()
        return any(phrase in transcript_lower for phrase in stop_phrases)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the voice loop."""
        return {
            "running": self._running,
            "state": self.state.value,
            "mode": self.config.mode.value,
            "stats": {
                "uptime_seconds": time.time() - self.stats.start_time if self.stats.start_time else 0,
                "total_interactions": self.stats.total_interactions,
                "successful_commands": self.stats.successful_commands,
                "failed_commands": self.stats.failed_commands,
            },
            "context": {
                "current_course_id": self.context.current_course_id,
                "current_session_id": self.context.current_session_id,
                "pending_confirmations": len(self.context.pending_confirmations),
            },
        }


# ============ Integration with voicemode MCP server ============

class VoiceModeIntegration:
    """
    Integration layer for the voicemode MCP server.
    
    This class provides the bridge between voicemode's audio handling
    and AristAI's command processing.
    """
    
    def __init__(self, controller: VoiceLoopController):
        """
        Initialize voicemode integration.
        
        Args:
            controller: The voice loop controller to use
        """
        self.controller = controller
        self._voicemode_client = None
    
    async def connect_to_voicemode(self, config: Dict[str, Any]):
        """
        Connect to the voicemode MCP server.
        
        Args:
            config: Configuration for voicemode connection
        """
        # This would initialize the connection to voicemode
        # The actual implementation depends on how voicemode exposes its API
        
        logger.info("Connecting to voicemode MCP server...")
        
        # Placeholder for voicemode integration
        # In reality, this would:
        # 1. Connect to voicemode server
        # 2. Configure audio settings
        # 3. Set up callbacks for transcripts
        
        pass
    
    async def handle_voicemode_transcript(self, transcript: str):
        """
        Handle a transcript received from voicemode.
        
        Args:
            transcript: The transcribed text from voicemode
        """
        # Process the command using the controller
        response = await self.controller._process_command(transcript)
        
        # Send response back through voicemode for TTS
        await self._send_to_voicemode_tts(response)
    
    async def _send_to_voicemode_tts(self, text: str):
        """Send text to voicemode for TTS."""
        # Placeholder for voicemode TTS integration
        pass


# ============ HTTP/WebSocket API for voice control ============

async def create_voice_api_router():
    """
    Create FastAPI router for voice control endpoints.
    
    This allows the frontend to control the voice loop via HTTP/WebSocket.
    """
    from fastapi import APIRouter, WebSocket, WebSocketDisconnect
    
    router = APIRouter()
    
    # Global controller instance (would be per-user in production)
    controller: Optional[VoiceLoopController] = None
    
    @router.post("/voice/start")
    async def start_voice_loop(config: Optional[Dict[str, Any]] = None):
        """Start the voice loop."""
        nonlocal controller
        
        if controller and controller._running:
            return {"status": "already_running", "message": "Voice loop is already running"}
        
        voice_config = VoiceConfig()
        if config:
            for key, value in config.items():
                if hasattr(voice_config, key):
                    setattr(voice_config, key, value)
        
        controller = VoiceLoopController(config=voice_config)
        
        # Start in background task
        asyncio.create_task(controller.start())
        
        return {"status": "started", "message": "Voice loop started"}
    
    @router.post("/voice/stop")
    async def stop_voice_loop():
        """Stop the voice loop."""
        nonlocal controller
        
        if not controller or not controller._running:
            return {"status": "not_running", "message": "Voice loop is not running"}
        
        await controller.stop()
        return {"status": "stopped", "message": "Voice loop stopped"}
    
    @router.get("/voice/status")
    async def get_voice_status():
        """Get voice loop status."""
        if not controller:
            return {"status": "not_initialized", "running": False}
        
        return controller.get_status()
    
    @router.post("/voice/command")
    async def process_voice_command(transcript: str):
        """
        Process a voice command directly (for testing or text fallback).
        
        This bypasses audio capture and directly processes a text command.
        """
        if not controller:
            # Create a temporary controller for one-off commands
            temp_controller = VoiceLoopController()
            response = await temp_controller._process_command(transcript)
            temp_controller._close_db()
            return {"transcript": transcript, "response": response}
        
        response = await controller._process_command(transcript)
        return {"transcript": transcript, "response": response}
    
    @router.websocket("/voice/ws")
    async def voice_websocket(websocket: WebSocket):
        """
        WebSocket endpoint for real-time voice interaction.
        
        Protocol:
        - Client sends: {"type": "audio", "data": "<base64 audio>"} or {"type": "text", "data": "<transcript>"}
        - Server sends: {"type": "transcript", "data": "<text>"} or {"type": "response", "data": "<text>"}
        """
        await websocket.accept()
        
        ws_controller = VoiceLoopController(
            on_transcript=lambda t: asyncio.create_task(
                websocket.send_json({"type": "transcript", "data": t})
            ),
            on_response=lambda r: asyncio.create_task(
                websocket.send_json({"type": "response", "data": r})
            ),
        )
        
        try:
            while True:
                data = await websocket.receive_json()
                
                if data.get("type") == "audio":
                    # Decode audio and transcribe
                    import base64
                    audio_bytes = base64.b64decode(data.get("data", ""))
                    result = asr.transcribe(audio_bytes)
                    
                    if result.transcript:
                        # Send transcript
                        await websocket.send_json({
                            "type": "transcript",
                            "data": result.transcript
                        })
                        
                        # Process command
                        response = await ws_controller._process_command(result.transcript)
                        await websocket.send_json({
                            "type": "response",
                            "data": response
                        })
                
                elif data.get("type") == "text":
                    # Direct text input
                    transcript = data.get("data", "")
                    if transcript:
                        response = await ws_controller._process_command(transcript)
                        await websocket.send_json({
                            "type": "response",
                            "data": response
                        })
                
                elif data.get("type") == "stop":
                    break
                    
        except WebSocketDisconnect:
            logger.info("Voice WebSocket disconnected")
        finally:
            ws_controller._close_db()
    
    return router


# ============ Main entry point for standalone voice loop ============

async def main():
    """Run the voice loop standalone (for testing)."""
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    
    print("AristAI Voice Loop Controller")
    print("=" * 40)
    print("Commands:")
    print("  Type a command to simulate voice input")
    print("  Type 'quit' to exit")
    print("=" * 40)
    
    controller = VoiceLoopController(
        config=VoiceConfig(mode=VoiceMode.CONTINUOUS),
        on_response=lambda r: print(f"\n🔊 AristAI: {r}\n"),
    )
    
    # Manual input loop for testing
    while True:
        try:
            user_input = input("🎤 You: ").strip()
            
            if user_input.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break
            
            if not user_input:
                continue
            
            response = await controller._process_command(user_input)
            print(f"\n🔊 AristAI: {response}\n")
            
        except KeyboardInterrupt:
            print("\nInterrupted. Goodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")
    
    controller._close_db()


if __name__ == "__main__":
    asyncio.run(main())
