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
        print(f"[GENERATE] title={request.course_title}, reference_file_id={request.reference_file_id}", flush=True)

        if request.reference_file_id:
            file_record = db.query(UploadedFile).filter(UploadedFile.id == request.reference_file_id).first()
            print(f"[GENERATE] Reference file record: {file_record.filename if file_record else 'NOT FOUND'}", flush=True)
            if file_record:
                try:
                    storage = StorageService()
                    content = storage.get_file(file_record.object_name)
                    print(f"[GENERATE] Storage returned content: {len(content) if content else 0} bytes", flush=True)
                    if content:
                        parsed_text = parse_file(file_record.filename, content)
                        print(f"[GENERATE] Parsed text length: {len(parsed_text)} chars", flush=True)
                        print(f"[GENERATE] First 300 chars: {parsed_text[:300]}", flush=True)
                        reference_context = f"\n\n--- REFERENCE DOCUMENT ({file_record.filename}) ---\n{parsed_text[:20000]}\n--- END REFERENCE DOCUMENT ---"
                except Exception as e:
                    print(f"[GENERATE] ERROR reading reference file: {e}", flush=True)
        else:
            print("[GENERATE] No reference_file_id provided", flush=True)

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
                "materials": "..."
            },
            "learning_goals": [
                { "id": 1, "text": "..." }
            ],
            "schedule": [
                { "week": "1", "topic": "...", "assignment": "..." }
            ],
            "policies": {
                "academic_integrity": "...",
                "attendance": "...",
                "accessibility": "...",
                "late_work": "...",
                "grading": "..."
            },
            "custom_sections": {
                "Section Name": "Full section content as a string..."
            }
        }

        Requirements:
        1. **Learning Outcomes**: Generate 5-7 specific, measurable goals using Bloom's Taxonomy verbs.
        2. **Schedule**: Create a week-by-week schedule matching the user's specified duration. Ensure a logical progression from foundational to advanced topics.
        3. **Materials**: Recommend high-quality, relevant textbooks and resources in the 'course_info.materials' field.
        4. **custom_sections**: Use this field to capture ANY content from the reference document that does not fit the standard fields above. Examples: office hours, grading breakdown, course materials lists, university-specific policies, diversity statements, mental health resources, technology requirements, communication guidelines, prerequisites, instructor bio, TA info, etc. Preserve the original section names as keys and their full content as values. Do NOT discard any reference content.
        5. **CRITICAL — Reference Document**: If a reference document is provided, it is the PRIMARY SOURCE. Your job is to DIGITIZE and STRUCTURE it, not replace it:
           - Map standard sections (title, schedule, goals, policies) to the standard fields
           - Map ALL other sections to custom_sections — do NOT discard any content
           - Preserve the original wording, details, and specificity from the reference
           - Do NOT invent new topics or generic content when the reference provides specific content
           - If the reference has placeholder text (e.g., "[Course Title]"), keep the placeholders
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

        print(f"[GENERATE] Sending to LLM: reference_context_length={len(reference_context)}, user_prompt_length={len(user_prompt)}", flush=True)

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
        print(f"[GENERATE] ERROR: {e}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))
