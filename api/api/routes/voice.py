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
    "syllabus": """Generate a comprehensive course syllabus for: {context}

You MUST output ONLY valid JSON matching this exact schema (no markdown, no explanations):
{{
  "course_info": {{
    "title": "Course Title",
    "code": "COURSE-101",
    "semester": "Fall 2024",
    "instructor": "TBD",
    "description": "2-3 sentence course description explaining what students will learn",
    "prerequisites": "List prerequisites or 'None'"
  }},
  "learning_goals": [
    "By the end of this course, students will be able to... (5-8 specific, measurable objectives)"
  ],
  "learning_resources": [
    "Textbook: Title by Author",
    "Online resources, articles, etc."
  ],
  "schedule": [
    {{"week": 1, "module": "Introduction", "topic": "Course overview and foundational concepts"}},
    {{"week": 2, "module": "Module Name", "topic": "Specific topic covered"}}
  ],
  "policies": {{
    "grading": "Assignments: 40%, Midterm: 25%, Final: 35%",
    "attendance": "Attendance policy description",
    "academic_integrity": "Academic honesty policy",
    "accessibility": "Accommodations available upon request",
    "office_hours": "TBD or by appointment"
  }}
}}

Generate a complete schedule with 10-14 weeks.
Include 5-8 learning goals.
Include 3-5 learning resources.
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

    # Delegate syllabus generation to the syllabus-tool API
    if data.content_type == "syllabus":
        from api.core.config import get_settings
        from api.services.syllabus_formatter import syllabus_json_to_text

        settings = get_settings()
        payload = {
            "course_title": data.context,
            "target_audience": "University students",
            "duration": "16 weeks",
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{settings.syllabus_tool_url}/api/v1/generate/draft",
                    json=payload,
                    timeout=120,
                )
                resp.raise_for_status()
                tool_data = resp.json()
        except Exception as exc:
            logger.error(f"[{request_id}] Syllabus tool error: {exc}")
            raise HTTPException(status_code=502, detail=f"Syllabus tool unavailable: {exc}")

        # Map syllabus-tool SyllabusData → forum SyllabusSchema format
        forum_json = {
            "course_info": {
                "title": tool_data.get("course_info", {}).get("title", data.context),
                "code": tool_data.get("course_info", {}).get("code"),
                "semester": tool_data.get("course_info", {}).get("semester"),
                "instructor": tool_data.get("course_info", {}).get("instructor"),
                "description": tool_data.get("course_info", {}).get("description", ""),
                "prerequisites": tool_data.get("course_info", {}).get("prerequisites"),
            },
            "learning_goals": [
                g["text"] if isinstance(g, dict) else g
                for g in tool_data.get("learning_goals", [])
            ],
            "learning_resources": [],
            "schedule": [
                {
                    "week": int(item["week"]) if str(item.get("week", "")).isdigit() else idx + 1,
                    "module": item.get("topic", ""),
                    "topic": item.get("topic", ""),
                }
                for idx, item in enumerate(tool_data.get("schedule", []))
            ],
            "policies": {
                "grading": tool_data.get("policies", {}).get("grading", ""),
                "attendance": tool_data.get("policies", {}).get("attendance", ""),
                "academic_integrity": tool_data.get("policies", {}).get("academic_integrity", ""),
                "accessibility": tool_data.get("policies", {}).get("accessibility"),
                "office_hours": None,
            },
        }

        # Extract learning_resources from course_info.materials
        materials = tool_data.get("course_info", {}).get("materials", "")
        if materials:
            forum_json["learning_resources"] = [
                line.strip() for line in materials.split("\n") if line.strip()
            ] or [materials]

        # Convert to display text using existing formatter
        syllabus_text = syllabus_json_to_text(forum_json, data.language)

        processing_time = time.time() - start_time
        logger.info(f"[{request_id}] Syllabus generated via syllabus-tool - schedule_items={len(forum_json['schedule'])}, time={processing_time:.2f}s")

        return {
            "content": syllabus_text,
            "content_type": "syllabus",
            "syllabus_json": forum_json,
            "source": "syllabus_tool",
            "schema_valid": True,
            "model": "syllabus-tool",
            "tokens_used": 0,
            "estimated_cost_usd": 0,
            "processing_time_seconds": round(processing_time, 2),
        }

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

    # Invoke LLM - use JSON mode for syllabus to guarantee valid JSON output
    use_json_mode = data.content_type == "syllabus"
    response = invoke_llm_with_metrics(llm, prompt, model_name, json_mode=use_json_mode)

    processing_time = time.time() - start_time

    if not response.success:
        logger.error(f"[{request_id}] LLM invocation failed: {response.metrics.error_message}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Content generation failed: {response.metrics.error_message}"
        )

    logger.info(f"[{request_id}] Content generated successfully - tokens={response.metrics.total_tokens}, cost=${response.metrics.estimated_cost_usd:.4f}, time={processing_time:.2f}s")

    # Special handling for syllabus - parse JSON and convert to text
    result = {
        "content": response.content,
        "content_type": data.content_type,
        "model": model_name,
        "tokens_used": response.metrics.total_tokens,
        "estimated_cost_usd": response.metrics.estimated_cost_usd,
        "processing_time_seconds": round(processing_time, 2),
    }

    if data.content_type == "syllabus":
        import json
        from api.services.syllabus_formatter import syllabus_json_to_text, validate_syllabus_json

        try:
            # Parse the JSON response
            raw_content = response.content.strip()
            # Remove markdown code blocks if present
            if raw_content.startswith("```"):
                raw_content = raw_content.split("```")[1]
                if raw_content.startswith("json"):
                    raw_content = raw_content[4:]
                raw_content = raw_content.strip()

            syllabus_json = json.loads(raw_content)

            # Validate against Pydantic schema to ensure structure matches template
            is_valid, validation_error = validate_syllabus_json(syllabus_json)
            if not is_valid:
                logger.warning(f"[{request_id}] Syllabus JSON validation warning: {validation_error}")
                # Still proceed - validation is lenient, JSON is usable

            # Convert to readable text for display
            syllabus_text = syllabus_json_to_text(syllabus_json, data.language)

            result["content"] = syllabus_text  # Text for display
            result["syllabus_json"] = syllabus_json  # Structured data for storage
            result["source"] = "structured_generation"
            result["schema_valid"] = is_valid  # Indicate if it passed strict schema validation

            logger.info(f"[{request_id}] Syllabus JSON parsed successfully with {len(syllabus_json.get('schedule', []))} schedule items, schema_valid={is_valid}")

        except json.JSONDecodeError as e:
            # If JSON parsing fails, return raw content as before
            logger.warning(f"[{request_id}] Failed to parse syllabus JSON: {e}. Returning raw content.")
            result["parse_warning"] = "Generated content was not valid JSON. Returned as raw text."

    return result


class SmartContextRequest(BaseModel):
    """Request for smart context from database."""
    query: str = Field(..., min_length=1, description="Natural language query about user's data")
    user_id: Optional[int] = Field(default=None, description="User ID for context")
    current_page: Optional[str] = Field(default=None, description="Current page path")


SMART_CONTEXT_PROMPT = """You are a helpful assistant that answers questions about a user's educational platform data.

Based on the query and available data, provide a concise, helpful response.

User's Query: {query}

Available Data:
{data}

Instructions:
- Answer the query directly and concisely
- If listing items, use a simple numbered or bulleted format
- If no relevant data, say so briefly
- Keep response under 100 words
"""


@router.post("/smart-context", status_code=status.HTTP_200_OK)
async def get_smart_context(request: Request, data: SmartContextRequest, db: Session = Depends(get_db)):
    """
    Get intelligent context from the database using LLM.

    This endpoint queries the database based on the user's natural language query
    and returns a smart, contextual response.
    """
    import time
    import uuid
    from api.models.course import Course
    from api.models.session import Session as SessionModel
    from api.models.enrollment import Enrollment

    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    logger.info(f"[{request_id}] POST /api/voice/smart-context - query='{data.query}'")

    # Simple auth check
    require_auth(request)

    # Get user_id from query param or request body
    user_id = data.user_id
    if not user_id:
        # Try to get from query params
        user_id = request.query_params.get('user_id')
        if user_id:
            user_id = int(user_id)

    # Gather relevant data based on query keywords
    context_data = []
    query_lower = data.query.lower()

    try:
        # Fetch courses if query mentions courses
        if any(word in query_lower for word in ['course', 'courses', 'class', 'classes', 'curso', 'cursos']):
            if user_id:
                courses = db.query(Course).filter(Course.created_by == user_id).all()
            else:
                courses = db.query(Course).limit(10).all()

            if courses:
                course_list = [f"- {c.title} (ID: {c.id}, Code: {c.join_code or 'N/A'})" for c in courses]
                context_data.append(f"User's Courses ({len(courses)}):\n" + "\n".join(course_list))

        # Fetch sessions if query mentions sessions
        if any(word in query_lower for word in ['session', 'sessions', 'class', 'sesión', 'sesiones']):
            if user_id:
                # Get sessions for user's courses
                user_courses = db.query(Course).filter(Course.created_by == user_id).all()
                course_ids = [c.id for c in user_courses]
                sessions = db.query(SessionModel).filter(SessionModel.course_id.in_(course_ids)).order_by(SessionModel.id.desc()).limit(20).all()
            else:
                sessions = db.query(SessionModel).limit(10).all()

            if sessions:
                session_list = [f"- {s.title} (Status: {s.status}, Course ID: {s.course_id})" for s in sessions]
                context_data.append(f"Sessions ({len(sessions)}):\n" + "\n".join(session_list))

        # Fetch enrollments if query mentions students or enrollment
        if any(word in query_lower for word in ['student', 'students', 'enrolled', 'enrollment', 'estudiante', 'estudiantes']):
            if user_id:
                user_courses = db.query(Course).filter(Course.created_by == user_id).all()
                course_ids = [c.id for c in user_courses]
                enrollments = db.query(Enrollment).filter(Enrollment.course_id.in_(course_ids)).limit(50).all()
            else:
                enrollments = db.query(Enrollment).limit(20).all()

            if enrollments:
                # Group by course
                by_course = {}
                for e in enrollments:
                    if e.course_id not in by_course:
                        by_course[e.course_id] = 0
                    by_course[e.course_id] += 1

                enrollment_summary = [f"- Course {cid}: {count} students" for cid, count in by_course.items()]
                context_data.append(f"Enrollments:\n" + "\n".join(enrollment_summary))

        # If no specific data found, provide general info
        if not context_data:
            if user_id:
                course_count = db.query(Course).filter(Course.created_by == user_id).count()
                context_data.append(f"User has {course_count} courses in total.")
            else:
                context_data.append("No specific data found for this query.")

    except Exception as e:
        logger.error(f"[{request_id}] Database query error: {e}")
        context_data.append(f"Error fetching data: {str(e)}")

    # Use LLM to generate a smart response
    llm, model_name = get_llm_with_tracking()
    if not llm:
        # Return raw data if no LLM configured
        return {
            "response": "\n\n".join(context_data),
            "raw_data": context_data,
            "model": None,
        }

    prompt = SMART_CONTEXT_PROMPT.format(
        query=data.query,
        data="\n\n".join(context_data) if context_data else "No data available."
    )

    llm_response = invoke_llm_with_metrics(llm, prompt, model_name)

    processing_time = time.time() - start_time

    if not llm_response.success:
        logger.error(f"[{request_id}] LLM error: {llm_response.metrics.error_message}")
        return {
            "response": "\n\n".join(context_data),
            "raw_data": context_data,
            "model": None,
            "error": llm_response.metrics.error_message,
        }

    logger.info(f"[{request_id}] Smart context generated - tokens={llm_response.metrics.total_tokens}, time={processing_time:.2f}s")

    return {
        "response": llm_response.content,
        "raw_data": context_data,
        "model": model_name,
        "tokens_used": llm_response.metrics.total_tokens,
        "processing_time_seconds": round(processing_time, 2),
    }
