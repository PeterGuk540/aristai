from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.uploaded_file import UploadedFile
from app.services.storage import StorageService
from app.services.parser import parse_file
from app.schemas.generator import GenerateRequest
from app.schemas.syllabus import SyllabusData, CourseInfo, LearningGoal, ScheduleItem, Policies
from app.services.llm_factory import invoke_llm
from langchain_core.messages import SystemMessage, HumanMessage
import json
import re
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/draft", response_model=SyllabusData)
async def generate_draft(request: GenerateRequest, db: Session = Depends(get_db)):
    try:
        reference_context = ""
        logger.info(f"Generate draft: title={request.course_title}, reference_file_id={request.reference_file_id}")

        if request.reference_file_id:
            file_record = db.query(UploadedFile).filter(UploadedFile.id == request.reference_file_id).first()
            logger.info(f"Reference file record: {file_record.filename if file_record else 'NOT FOUND'}")
            if file_record:
                try:
                    storage = StorageService()
                    content = storage.get_file(file_record.object_name)
                    logger.info(f"Storage returned content: {len(content) if content else 0} bytes")
                    if content:
                        parsed_text = parse_file(file_record.filename, content)
                        logger.info(f"Parsed text length: {len(parsed_text)} chars, first 200: {parsed_text[:200]}")
                        reference_context = f"\n\n--- REFERENCE DOCUMENT ({file_record.filename}) ---\n{parsed_text[:20000]}\n--- END REFERENCE DOCUMENT ---"
                except Exception as e:
                    logger.error(f"Error reading reference file: {e}", exc_info=True)
        else:
            logger.info("No reference_file_id provided in request")

        system_prompt = """You are an expert curriculum designer. Your task is to generate a comprehensive syllabus draft based on the user's brief course description and optional reference material.

        You MUST return ONLY a valid JSON object matching the following structure. Do not include any markdown formatting like ```json ... ``` or potential chat text. Just the raw JSON string.

        Structure:
        {
            "course_info": {
                "title": "...",
                "code": "...",
                "instructor": "[Instructor Name]",
                "semester": "[Semester]",
                "description": "...",
                "format": "...",
                "materials": "..."  // Recommend 2-3 classic textbooks and 1-2 online resources here
            },
            "learning_goals": [
                { "id": 1, "text": "..." } // Use Bloom's Taxonomy (e.g., Analyze, Evaluate, Create)
            ],
            "schedule": [
                { "week": "1", "topic": "...", "assignment": "..." } // Distribute difficult topics reasonably over the duration
            ],
            "policies": {
                "academic_integrity": "Standard academic integrity policy...",
                "attendance": "Standard attendance policy...",
                "accessibility": "Standard accessibility accommodation policy...",
                "late_work": "Standard late work policy...",
                "grading": "Standard grading scale..."
            }
        }

        Requirements:
        1. **Learning Outcomes**: Generate 5-7 specific, measurable goals using Bloom's Taxonomy verbs.
        2. **Schedule**: Create a week-by-week schedule matching the user's specified duration. Ensure a logical progression from foundational to advanced topics.
        3. **Materials**: Recommend high-quality, relevant textbooks and resources in the 'course_info.materials' field.
        4. **CRITICAL — Reference Document**: If a reference document is provided, you MUST use it as the primary basis for the syllabus. Extract and preserve its topics, structure, schedule, learning goals, and policies as closely as possible. Adapt the content to fit the JSON schema, but do NOT invent new topics or ignore the reference material. The reference document is the instructor's existing syllabus or template — your job is to digitize and structure it, not replace it.
        """

        if reference_context:
            user_prompt = f"""
        Course Title: {request.course_title}
        Target Audience: {request.target_audience}
        Duration: {request.duration}
        {reference_context}

        IMPORTANT: A reference document has been provided above. Use it as the primary source — extract its topics, schedule, learning goals, and policies. Structure the content into the required JSON format while preserving the original material as faithfully as possible.
        """
        else:
            user_prompt = f"""
        Course Title: {request.course_title}
        Target Audience: {request.target_audience}
        Duration: {request.duration}

        Please generate a full syllabus structure for this course from scratch.
        """

        logger.info(f"Sending to LLM: reference_context_length={len(reference_context)}, user_prompt_length={len(user_prompt)}")

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        response = invoke_llm(messages)
        content = response.content

        # cleanup code blocks if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
             content = content.split("```")[1].split("```")[0]

        data = json.loads(content.strip())

        # Ensure IDs in learning goals
        for idx, goal in enumerate(data.get("learning_goals", [])):
            goal["id"] = idx + 1

        return data

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to generate valid JSON content from AI.")
    except Exception as e:
        logger.error(f"Generate draft error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
