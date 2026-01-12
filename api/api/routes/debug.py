from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from api.core.database import get_db

router = APIRouter()


@router.get("/db_check")
def check_database(db: Session = Depends(get_db)):
    """Check database connectivity."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception:
        return {"status": "error", "database": "connection failed"}


@router.post("/enqueue_test_task")
def enqueue_test_task():
    """Enqueue a test task to validate Celery worker connectivity."""
    from worker.tasks import test_task

    task = test_task.delay("hello from API")
    return {"task_id": task.id, "status": "queued"}


@router.get("/task_status/{task_id}")
def get_task_status(task_id: str):
    """Check the status of a Celery task."""
    from worker.celery_app import celery_app

    task = celery_app.AsyncResult(task_id)
    response = {
        "task_id": task_id,
        "status": task.status,
    }
    # Only include result if task succeeded (avoid exposing error details)
    if task.successful():
        response["result"] = task.result
    return response
