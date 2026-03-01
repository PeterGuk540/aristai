from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class PolicyBase(BaseModel):
    category: str
    content: str

class PolicyCreate(PolicyBase):
    pass

class PolicyUpdate(PolicyBase):
    category: Optional[str] = None
    content: Optional[str] = None

class Policy(PolicyBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class PolicyAuditRequest(BaseModel):
    syllabus_text: str
    policy_category: Optional[str] = None

class PolicyAuditResponse(BaseModel):
    compliance_score: int
    missing_points: List[str]
    suggestions: List[str]
