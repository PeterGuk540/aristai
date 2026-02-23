"""
Voice Assistant API routes.

Endpoints for ElevenLabs Agent:
    GET  /api/voice/agent/signed-url - Get signed WebSocket URL for ElevenLabs Agent
    GET  /api/voice/agent/test        - Test endpoint
    POST /api/voice/generate-content  - Generate AI content (syllabus, objectives, etc.)

Legacy TTS endpoints removed - using ElevenLabs Agent realtime conversation
"""
import logging
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
import httpx
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.api.routes.ui_actions import broker
from api.api.voice_converse_router import ConverseRequest, voice_converse
from api.core.database import get_db
from api.services.elevenlabs_agent import get_signed_url
from api.services.tool_response import normalize_tool_result
from workflows.llm_utils import get_llm_with_tracking, invoke_llm_with_metrics

logger = logging.getLogger(__name__)

# Legacy exports removed - ElevenLabs Agents integration uses new endpoints
router = APIRouter()

class DelegateRequest(BaseModel):
    transcript: str = Field(..., min_length=1)
    current_page: Optional[str] = None
    user_id: Optional[int] = None
    context: Optional[list[str]] = None


class GenerateContentRequest(BaseModel):
    """Request for AI content generation."""
    content_type: Literal["syllabus", "objectives", "description", "poll_question", "case_study", "summary"] = Field(
        ..., description="Type of content to generate"
    )
    context: str = Field(..., min_length=1, description="Context for generation (e.g., course title, topic)")
    language: str = Field(default="en", description="Language for generated content (en or es)")
    additional_instructions: Optional[str] = Field(default=None, description="Additional instructions for generation")


def require_auth(request: Request) -> bool:
    """
    Simple authentication check.
    TODO: Validate Cognito JWT properly later.
    For now, just check for Authorization header presence.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
        )
    # TODO: Add proper JWT validation when Cognito is integrated
    # TODO: Implement full Cognito JWT verification for production
    return True

# Legacy TTS endpoint removed - use ElevenLabs Agents realtime conversation instead
# @router.post("/synthesize", response_model=None)
# async def voice_synthesize(request: Request):
#     """LEGACY: Standard TTS endpoint - DEPRECATED"""
#     # This endpoint is removed for production deployment
#     # Use GET /api/voice/agent/signed-url + official SDK instead


# Legacy voice endpoints (transcribe, plan, execute) removed
# Using ElevenLabs Agent realtime conversation instead


# Legacy TTS endpoint removed - use ElevenLabs Agents realtime conversation instead
# @router.post("/synthesize")
# async def voice_synthesize(request: Request):
#     """Standard TTS endpoint for frontend voice components."""
#     try:
#         logger.info("=== VOICE SYNTHESIS REQUEST ===")
#         data = await request.json()
#         text = data.get("text", "")
#         logger.info(f"Text to synthesize: {text}")
#         
#         if not text:
#             logger.warning("Empty text received")
#             raise HTTPException(status_code=400, detail="Text is required")
#         
#         logger.info("Calling TTS service...")
#         result = tts.synthesize(text)
#         logger.info(f"TTS success: {len(result.audio_bytes)} bytes, type: {result.content_type}")
#         
#         return Response(
#             content=result.audio_bytes,
#             media_type=result.content_type,
#             headers={"Cache-Control": "no-cache"}
#         )
#     except Exception as e:
#         logger.error(f"TTS synthesis failed: {type(e).__name__}: {str(e)}")
#         import traceback
#         logger.error(f"Full traceback: {traceback.format_exc()}")
#         raise HTTPException(status_code=500, detail=f"Voice synthesis error: {str(e)}")


# Legacy audit endpoint removed - no longer needed with ElevenLabs Agent


@router.get("/agent/test")
async def test_route():
    """Test route to verify router is working."""
    return {"message": "Router is working", "status": "ok"}

@router.get("/agent/signed-url", status_code=status.HTTP_200_OK)
async def get_agent_signed_url(request: Request, language: str = "en"):
    """
    Get a signed WebSocket URL for ElevenLabs Agent conversation.

    The browser will connect directly to ElevenLabs using this URL.
    The API key and agent ID are kept server-side.

    Args:
        language: Language code ('en' or 'es') for the agent to use
    """
    import time
    import uuid
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    logger.info(f"[{request_id}] GET /api/voice/agent/signed-url - Processing request (language={language})")

    # Simple authentication check
    require_auth(request)
    logger.info(f"[{request_id}] Authentication passed")

    try:
        signed_url = await get_signed_url(language=language)
        processing_time = time.time() - start_time
        logger.info(f"[{request_id}] Signed URL generated successfully - processing_time: {processing_time:.2f}s")
        return {"signed_url": signed_url}
    except ValueError as e:
        processing_time = time.time() - start_time
        logger.error(f"[{request_id}] Configuration error - processing_time: {processing_time:.2f}s - error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except httpx.HTTPStatusError as e:
        processing_time = time.time() - start_time
        logger.error(f"[{request_id}] ElevenLabs API error - processing_time: {processing_time:.2f}s - status: {e.response.status_code}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream service error: {e.response.text}"
        )
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"[{request_id}] Unexpected error - processing_time: {processing_time:.2f}s - error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/agent/delegate", status_code=status.HTTP_200_OK)
async def delegate_to_mcp(request: Request, db: Session = Depends(get_db)):
    """
    Delegate ElevenLabs agent tool calls to the MCP voice orchestrator.

    The ElevenLabs agent should define a single tool (delegate_to_mcp) that
    forwards transcript/current_page here. We execute MCP logic and return the
    response for the agent to speak, while streaming any UI actions to clients.
    """
    payload = await request.json()
    parameters = payload.get("parameters") or payload.get("arguments") or payload
    data = DelegateRequest(**parameters)

    response = await voice_converse(
        ConverseRequest(
            transcript=data.transcript,
            context=data.context,
            user_id=data.user_id,
            current_page=data.current_page,
        ),
        db=db,
    )

    ui_actions: list[dict] = []
    if response.action and response.action.type == "navigate" and response.action.target:
        ui_actions.append({"type": "ui.navigate", "payload": {"path": response.action.target}})

    if response.results:
        for item in response.results:
            if not isinstance(item, dict):
                continue
            normalized = normalize_tool_result(item, item.get("tool", "mcp"))
            ui_actions.extend(normalized.get("ui_actions") or [])

    for action in ui_actions:
        await broker.publish(data.user_id, action)

    return {
        "result": response.message,
        "message": response.message,
        "voice_response": response.message,
        "ui_actions": ui_actions,
        "results": response.results,
        "suggestions": response.suggestions,
    }


# Content generation prompts for different types
CONTENT_PROMPTS = {
    "syllabus": """Create a comprehensive course syllabus for: {context}

Include:
- Course overview (2-3 sentences)
- Weekly topics (8-12 weeks)
- Key readings or resources for each week
- Assessment methods

Format as clean text, one topic per line for the weekly schedule.
{additional}""",

    "objectives": """Generate 5-7 clear learning objectives for: {context}

Requirements:
- Start each objective with an action verb (Understand, Apply, Analyze, Create, Evaluate)
- Be specific and measurable
- One objective per line

{additional}""",

    "description": """Write a compelling course description for: {context}

Include:
- What students will learn
- Why this topic matters
- Prerequisites if any
- Target audience

Keep it concise (150-200 words).
{additional}""",

    "poll_question": """Create an engaging poll question for a class discussion about: {context}

Requirements:
- One clear question
- 3-4 answer options (on separate lines, prefixed with letters A, B, C, D)
- Options should be substantive, not just yes/no

{additional}""",

    "case_study": """Create a brief case study prompt for class discussion about: {context}

Include:
- A realistic scenario (3-4 sentences)
- Key decision point or dilemma
- 2-3 discussion questions

{additional}""",

    "summary": """Summarize the following content concisely: {context}

Keep it to 3-5 key points.
{additional}""",
}


@router.post("/generate-content", status_code=status.HTTP_200_OK)
async def generate_content(request: Request, data: GenerateContentRequest):
    """
    Generate AI content for courses (syllabus, objectives, etc.) using OpenAI.

    This endpoint is called by the ElevenLabs voice assistant's generate_content tool.
    """
    import time
    import uuid
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    logger.info(f"[{request_id}] POST /api/voice/generate-content - type={data.content_type}, language={data.language}")

    # Simple auth check
    require_auth(request)

    # Get LLM
    llm, model_name = get_llm_with_tracking()
    if not llm:
        logger.error(f"[{request_id}] No LLM API key configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service not configured. Please set OPENAI_API_KEY or ANTHROPIC_API_KEY."
        )

    # Build prompt
    prompt_template = CONTENT_PROMPTS.get(data.content_type)
    if not prompt_template:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown content type: {data.content_type}"
        )

    additional = f"\nAdditional instructions: {data.additional_instructions}" if data.additional_instructions else ""

    # Add language instruction
    language_instruction = ""
    if data.language == "es":
        language_instruction = "\n\nIMPORTANT: Generate the content in Spanish."

    prompt = prompt_template.format(
        context=data.context,
        additional=additional
    ) + language_instruction

    logger.info(f"[{request_id}] Invoking {model_name} for {data.content_type} generation")

    # Invoke LLM
    response = invoke_llm_with_metrics(llm, prompt, model_name)

    processing_time = time.time() - start_time

    if not response.success:
        logger.error(f"[{request_id}] LLM invocation failed: {response.metrics.error_message}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Content generation failed: {response.metrics.error_message}"
        )

    logger.info(f"[{request_id}] Content generated successfully - tokens={response.metrics.total_tokens}, cost=${response.metrics.estimated_cost_usd:.4f}, time={processing_time:.2f}s")

    return {
        "content": response.content,
        "content_type": data.content_type,
        "model": model_name,
        "tokens_used": response.metrics.total_tokens,
        "estimated_cost_usd": response.metrics.estimated_cost_usd,
        "processing_time_seconds": round(processing_time, 2),
    }
