from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    context: str | None = None  # To pass current syllabus data if needed

class ChatResponse(BaseModel):
    response: str
    suggested_changes: dict | None = None
