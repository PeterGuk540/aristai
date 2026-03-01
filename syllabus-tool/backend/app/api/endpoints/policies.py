from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import json

from app.db.session import get_db
from app.models.standard_policy import StandardPolicy
from app.schemas.policy import Policy, PolicyCreate, PolicyUpdate, PolicyAuditRequest, PolicyAuditResponse
from app.services.llm_factory import invoke_llm
from langchain_core.messages import HumanMessage, SystemMessage

router = APIRouter()

@router.post("/", response_model=Policy)
def create_policy(policy: PolicyCreate, db: Session = Depends(get_db)):
    db_policy = StandardPolicy(**policy.dict())
    db.add(db_policy)
    db.commit()
    db.refresh(db_policy)
    return db_policy

@router.get("/", response_model=List[Policy])
def read_policies(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    policies = db.query(StandardPolicy).offset(skip).limit(limit).all()
    return policies

@router.get("/{policy_id}", response_model=Policy)
def read_policy(policy_id: int, db: Session = Depends(get_db)):
    policy = db.query(StandardPolicy).filter(StandardPolicy.id == policy_id).first()
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy

@router.put("/{policy_id}", response_model=Policy)
def update_policy(policy_id: int, policy: PolicyUpdate, db: Session = Depends(get_db)):
    db_policy = db.query(StandardPolicy).filter(StandardPolicy.id == policy_id).first()
    if db_policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    update_data = policy.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_policy, key, value)
    
    db.add(db_policy)
    db.commit()
    db.refresh(db_policy)
    return db_policy

@router.delete("/{policy_id}", response_model=Policy)
def delete_policy(policy_id: int, db: Session = Depends(get_db)):
    db_policy = db.query(StandardPolicy).filter(StandardPolicy.id == policy_id).first()
    if db_policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    db.delete(db_policy)
    db.commit()
    return db_policy

@router.post("/audit", response_model=PolicyAuditResponse)
def audit_policy(request: PolicyAuditRequest, db: Session = Depends(get_db)):
    # Fetch relevant standard policies
    query = db.query(StandardPolicy)
    if request.policy_category:
        query = query.filter(StandardPolicy.category == request.policy_category)
    standard_policies = query.all()
    
    if not standard_policies:
        return PolicyAuditResponse(
            compliance_score=100,
            missing_points=[],
            suggestions=["No standard policies found for comparison."]
        )

    standard_text = "\n\n".join([f"Category: {p.category}\nPolicy: {p.content}" for p in standard_policies])
    
    prompt = f"""
    You are a university policy auditor. Compare the following Syllabus Text against the Standard Policies.
    
    Standard Policies:
    {standard_text}
    
    Syllabus Text:
    {request.syllabus_text}
    
    Analyze the syllabus for compliance with the standard policies.
    Return a JSON object with the following fields:
    - compliance_score (integer 0-100)
    - missing_points (list of strings, specific requirements from standard policies missing in syllabus)
    - suggestions (list of strings, how to fix the missing points)
    
    Output ONLY valid JSON.
    """
    
    messages = [
        SystemMessage(content="You are a helpful assistant that outputs JSON."),
        HumanMessage(content=prompt)
    ]
    
    response = invoke_llm(messages)
    content = response.content
    
    # Basic cleanup for JSON parsing
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
        
    try:
        result = json.loads(content.strip())
        return PolicyAuditResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse LLM response: {str(e)}")
