from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.schemas.chat import ChatRequest
from app.services.llm_factory import get_llm
from langchain_core.messages import HumanMessage, SystemMessage
import json
import asyncio

router = APIRouter()

@router.post("/chat")
async def chat(request: ChatRequest):
    try:
        system_prompt = """You are a helpful assistant for a syllabus tool. You help teachers refine their course syllabi. 
        
        If the user asks you to modify, update, or rewrite parts of the syllabus, you MUST provide the structured data for the changes in a JSON block at the end of your response.
        
        The JSON structure should match this format (only include fields you are changing):
        ```json
        {
            "course_info": {
                "title": "...",
                "instructor": "..."
            },
            "learning_goals": [
                { "id": 1, "text": "..." }
            ],
            "schedule": [
                { "week": "1", "topic": "..." }
            ],
            "policies": {
                "attendance": "..."
            }
        }
        ```
        
        For example, if the user says "Change instructor to Dr. Smith", your response should be:
        "Sure, I've updated the instructor to Dr. Smith.
        ```json
        {
            "course_info": { "instructor": "Dr. Smith" }
        }
        ```
        
        Keep your text response concise and helpful.
        """
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=request.message)
        ]
        
        if request.context:
            context_str = f"\n\nCurrent Syllabus Context: {request.context}"
            messages[0].content += context_str

        llm = get_llm()
        
        async def generate():
            async for chunk in llm.astream(messages):
                yield chunk.content

        return StreamingResponse(generate(), media_type="text/plain")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
