from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.sql import func
from app.core.config import settings
from app.db.session import engine, get_db

from app.db.base import Base
from app.models.syllabus import Syllabus
from app.models.uploaded_file import UploadedFile
from app.models.analysis_history import AnalysisHistory
from app.models.standard_policy import StandardPolicy
from app.services.storage import storage_service
from app.services.parser import parse_file, extract_metadata, extract_syllabus_data, merge_structured_data
from app.services.converter import convert_to_pdf
from app.api.endpoints import chat, export, policies, regenerate, generate
from app.core.logger import log, log_step, log_buffer, setup_logging
from pydantic import BaseModel

# Create tables
Base.metadata.create_all(bind=engine)

# Initialize logging
setup_logging()

app = FastAPI(title=settings.PROJECT_NAME)

# Include routers
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(export.router, prefix="/api/v1", tags=["export"])
app.include_router(regenerate.router, prefix="/api/v1", tags=["regenerate"])
app.include_router(policies.router, prefix="/api/v1/policies", tags=["policies"])
app.include_router(generate.router, prefix="/api/v1/generate", tags=["generate"])

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list or ["*"],
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to Syllabus Tool API"}

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        # Try to query the database
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected", "minio": "configured"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

@app.get("/api/v1/health")
def health_check_v1(db: Session = Depends(get_db)):
    return health_check(db)

@app.get("/api/v1/logs")
def get_logs():
    return log_buffer.get_logs()

@app.post("/api/v1/upload/")
async def upload_files(
    files: List[UploadFile] = File(...),
    category: str = Form(...),
    db: Session = Depends(get_db)
):
    log_step(f"Starting upload for {len(files)} files in category: {category}")
    results = []
    for file in files:
        content = await file.read()
        filename = file.filename
        log_step(f"Processing file: {filename}")
        
        # Determine version
        last_version = db.query(func.max(UploadedFile.version)).filter(UploadedFile.filename == filename).scalar()
        new_version = (last_version or 0) + 1
        
        # Create unique object name for storage
        object_name_key = f"{filename}_v{new_version}"
        object_name = storage_service.upload_file(object_name_key, content, file.content_type)
        
        preview_object_name = None
        # Convert to PDF if it's a docx
        if filename.lower().endswith(".docx"):
            pdf_content = convert_to_pdf(content, filename)
            if pdf_content:
                preview_key = f"{filename}_v{new_version}_preview.pdf"
                preview_object_name = storage_service.upload_file(preview_key, pdf_content, "application/pdf")
        
        if object_name:
            log_step(f"File {filename} uploaded to storage. Parsing content...")
            extracted_text = parse_file(filename, content)
            metadata = extract_metadata(filename, extracted_text)
            
            db_file = UploadedFile(
                filename=filename,
                version=new_version,
                object_name=object_name,
                preview_object_name=preview_object_name,
                category=category,
                school=metadata["school"],
                department=metadata["department"],
                subject=metadata["subject"]
            )
            db.add(db_file)
            
            try:
                db.commit()
                db.refresh(db_file)
            except Exception as e:
                db.rollback()
                print(f"DB Error: {e}")

            results.append({
                "id": db_file.id,
                "filename": filename,
                "version": new_version,
                "status": "uploaded",
                "metadata": metadata,
                "extracted_text": extracted_text
            })
            log_step(f"File {filename} processed successfully.")
    
    return results

@app.get("/api/v1/files/")
def list_files(db: Session = Depends(get_db)):
    files = db.query(UploadedFile).order_by(UploadedFile.filename, UploadedFile.version.desc()).all()
    return files

@app.get("/api/v1/files/{file_id}/content")
def get_file_content(file_id: int, preview: bool = False, db: Session = Depends(get_db)):
    db_file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    target_object_name = db_file.object_name
    media_type = "application/octet-stream"
    
    if preview and db_file.preview_object_name:
        target_object_name = db_file.preview_object_name
        media_type = "application/pdf"
    elif db_file.filename.lower().endswith(".pdf"):
        media_type = "application/pdf"
    
    content = storage_service.get_file(target_object_name)
    if not content:
        raise HTTPException(status_code=404, detail="File content not found in storage")
    
    return Response(content=content, media_type=media_type)

@app.get("/api/v1/files/{file_id}/analyze")
def analyze_file(file_id: int, db: Session = Depends(get_db)):
    # Check DB first
    db_file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    content = storage_service.get_file(db_file.object_name)
    if not content:
        raise HTTPException(status_code=404, detail="File content not found in storage")
    
    extracted_text = parse_file(db_file.filename, content)
    
    # Check if we already have parsed data
    if db_file.parsed_data:
        return {
            "id": db_file.id,
            "filename": db_file.filename, 
            "version": db_file.version,
            "extracted_text": extracted_text,
            "structured_data": db_file.parsed_data
        }
    
    # Run structured extraction
    structured_data = extract_syllabus_data(extracted_text)
    
    # Update DB
    db_file.parsed_data = structured_data
    db_file.status = "processed"
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"DB Error updating parsed data: {e}")
        
    return {
        "id": db_file.id,
        "filename": db_file.filename, 
        "version": db_file.version,
        "extracted_text": extracted_text,
        "structured_data": structured_data
    }

@app.delete("/api/v1/files/{file_id}")
def delete_file(file_id: int, db: Session = Depends(get_db)):
    # Delete from DB
    db_file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    object_name = db_file.object_name
    db.delete(db_file)
    db.commit()
    
    # Delete from Storage
    if object_name:
        storage_service.delete_file(object_name)
    
    return {"message": "File deleted successfully"}

class AnalyzeBatchRequest(BaseModel):
    file_ids: List[int]
    guidance_file_id: Optional[int] = None
    template_id: str = "BGSU_Standard"

@app.post("/api/v1/analyze_batch/")
async def analyze_batch(request: AnalyzeBatchRequest, db: Session = Depends(get_db)):
    log_step(f"Starting batch analysis for {len(request.file_ids)} files.")
    # Check for existing cache (skip if guidance is used)
    if not request.guidance_file_id:
        histories = db.query(AnalysisHistory).filter(AnalysisHistory.is_deleted == False).order_by(AnalysisHistory.created_at.desc()).all()
        request_file_ids_set = set(request.file_ids)
        
        for history in histories:
            if history.file_ids and set(history.file_ids) == request_file_ids_set:
                log_step("Found cached analysis result. Returning cached data.")
                return {
                    "combined_text": history.combined_text,
                    "structured_data": history.structured_data
                }

    combined_text = ""
    last_structured_data = None
    
    guidance_text = None
    if request.guidance_file_id:
        guidance_file = db.query(UploadedFile).filter(UploadedFile.id == request.guidance_file_id).first()
        if guidance_file:
            log_step(f"Loading guidance file: {guidance_file.filename}")
            guidance_content = storage_service.get_file(guidance_file.object_name)
            if guidance_content:
                guidance_text = parse_file(guidance_file.filename, guidance_content)
    
    # Verify files exist
    files = db.query(UploadedFile).filter(UploadedFile.id.in_(request.file_ids)).all()
    
    # Prepare tasks for parallel execution
    import concurrent.futures
    
    # Helper function for processing a single file
    def process_file_task(file_data):
        f_id, f_name, f_obj_name, f_ver = file_data
        # Note: Cannot use async log here easily as it runs in thread pool
        content = storage_service.get_file(f_obj_name)
        if not content:
            return f_id, None, None
        
        ext_text = parse_file(f_name, content)
        struct_data = extract_syllabus_data(ext_text, guidance_text, request.template_id)
        return f_id, ext_text, struct_data

    # Extract necessary data from DB objects to pass to threads
    file_tasks_data = [(f.id, f.filename, f.object_name, f.version) for f in files]
    
    results_map = {}
    
    log_step("Processing files in parallel...")
    
    # Execute in parallel
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_file = {executor.submit(process_file_task, f_data): f_data for f_data in file_tasks_data}
        for future in concurrent.futures.as_completed(future_to_file):
            f_id, ext_text, struct_data = future.result()
            if ext_text and struct_data:
                results_map[f_id] = (ext_text, struct_data)
                # We can log here since we are back in the main loop (but wait, this is blocking)
                # Actually analyze_batch is async now, but the executor blocks. 
                # We should ideally run this in a way that doesn't block the event loop if we want real-time logs during processing.
                # But for now, we will log after completion of each.

    # Process results in the original order (or just iterate through files list)
    for db_file in files:
        if db_file.id in results_map:
            log_step(f"Analysis complete for {db_file.filename}")
            extracted_text, structured_data = results_map[db_file.id]
            
            combined_text += f"\n\n--- Content of {db_file.filename} (v{db_file.version}) ---\n{extracted_text}"
            
            # Merge with previous data
            if last_structured_data:
                log_step(f"Merging results for {db_file.filename}...")
                last_structured_data = merge_structured_data(last_structured_data, structured_data)
            else:
                last_structured_data = structured_data
            
            # Update individual file status
            db_file.parsed_data = structured_data
            db_file.status = "processed"
            try:
                db.commit()
            except Exception as e:
                db.rollback()
                print(f"DB Error updating parsed data: {e}")

    log_step("Batch analysis completed successfully.")
    return {
        "combined_text": combined_text,
        "structured_data": last_structured_data
    }

class CreateHistoryRequest(BaseModel):
    file_ids: List[int]
    combined_text: str
    structured_data: dict

@app.post("/api/v1/analysis_history/")
def create_analysis_history(request: CreateHistoryRequest, db: Session = Depends(get_db)):
    # Get filenames for display
    files = db.query(UploadedFile).filter(UploadedFile.id.in_(request.file_ids)).all()
    file_names = [f"{f.filename} (v{f.version})" for f in files]

    # Use China Standard Time (UTC+8)
    tz_cn = timezone(timedelta(hours=8))
    created_at = datetime.now(tz_cn)

    history = AnalysisHistory(
        file_ids=request.file_ids,
        file_names=file_names,
        combined_text=request.combined_text,
        structured_data=request.structured_data,
        created_at=created_at
    )
    db.add(history)
    db.commit()
    db.refresh(history)
    return history

@app.get("/api/v1/analysis_history/")
def get_analysis_history(db: Session = Depends(get_db)):
    history = db.query(AnalysisHistory).filter(AnalysisHistory.is_deleted == False).order_by(AnalysisHistory.created_at.desc()).all()
    return history

@app.delete("/api/v1/analysis_history/{history_id}")
def delete_analysis_history(history_id: int, db: Session = Depends(get_db)):
    history = db.query(AnalysisHistory).filter(AnalysisHistory.id == history_id).first()
    if not history:
        raise HTTPException(status_code=404, detail="History item not found")
    
    history.is_deleted = True
    db.commit()
    return {"message": "History item deleted successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
