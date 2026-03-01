from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from app.db.session import get_db
from app.models.uploaded_file import UploadedFile
from app.services.storage import storage_service
from app.services.parser import parse_file
from app.services.llm_factory import invoke_llm
from langchain_core.messages import HumanMessage, SystemMessage

router = APIRouter()

class RegenerateRequest(BaseModel):
    file_ids: List[int]
    section: str  # "course_info", "policies", "schedule", "learning_goals"
    field: str    # "instructor", "attendance", "topic", "text", etc.
    item_context: Optional[Dict[str, Any]] = None  # For list items, e.g. {"week": "1"}
    instruction: Optional[str] = None  # Optional user instruction

@router.post("/regenerate")
def regenerate_field(request: RegenerateRequest, db: Session = Depends(get_db)):
    # 1. Fetch file content
    files = db.query(UploadedFile).filter(UploadedFile.id.in_(request.file_ids)).all()
    if not files:
        raise HTTPException(status_code=404, detail="Files not found")
    
    full_text = ""
    for file in files:
        content = storage_service.get_file(file.object_name)
        if content:
            text = parse_file(file.filename, content)
            full_text += f"\n\n--- {file.filename} ---\n{text}"
            
    if not full_text:
        raise HTTPException(status_code=404, detail="Could not extract text from files")

    # 2. Construct Prompt
    system_prompt = "You are a helpful assistant that extracts specific information from a syllabus."
    user_prompt = f"Here is the syllabus text:\n{full_text}\n\n"
    
    target_description = ""
    
    if request.section == "course_info":
        target_description = f"Please extract the '{request.field}' from the Course Information section."
    elif request.section == "policies":
        target_description = f"Please extract the '{request.field}' policy."
    elif request.section == "schedule":
        week = "Unknown"
        date = ""
        if request.item_context:
            week = request.item_context.get("week", "Unknown")
            date = request.item_context.get("date", "")
            
        target_description = f"Find the schedule entry for Week '{week}'"
        if date:
            target_description += f" (Date: {date})"
        target_description += f". Then extract the '{request.field}' for that entry."
    elif request.section == "learning_goals":
        if request.item_context:
            goal_id = request.item_context.get("id", "Unknown")
            target_description = f"Find the learning goal/objective number {goal_id}. Extract its text."
        else:
            target_description = "Extract all learning goals/objectives. Return them as a newline-separated list."
    else:
        target_description = f"Extract the '{request.field}' from the '{request.section}' section."
        
    user_prompt += f"Task: {target_description}\n"
    
    if request.instruction:
        user_prompt += f"Additional Instruction: {request.instruction}\n"
        
    user_prompt += "\nReturn ONLY the extracted value as a plain string. Do not wrap it in quotes or JSON. Do not add conversational filler."

    # 3. Call LLM
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]
    
    try:
        response = invoke_llm(messages)
        result = response.content.strip()
        # Remove quotes if LLM added them
        if result.startswith('"') and result.endswith('"'):
            result = result[1:-1]
        return {"value": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
