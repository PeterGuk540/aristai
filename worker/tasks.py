from worker.celery_app import celery_app


@celery_app.task(bind=True)
def test_task(self, message: str) -> dict:
    """Simple test task to verify Celery connectivity."""
    return {"message": f"Received: {message}", "task_id": self.request.id}


@celery_app.task(bind=True)
def generate_plans_task(self, course_id: int) -> dict:
    """Generate session plans from course syllabus using LLM workflow."""
    # Import here to avoid circular imports and ensure DB connection
    from workflows.planning import run_planning_workflow

    result = run_planning_workflow(course_id)
    return {"course_id": course_id, "status": "completed", "result": result}


@celery_app.task(bind=True)
def start_live_copilot_task(self, session_id: int) -> dict:
    """Start live instructor copilot for a session."""
    from workflows.copilot import run_copilot_workflow

    result = run_copilot_workflow(session_id)
    return {"session_id": session_id, "status": "completed", "result": result}


@celery_app.task(bind=True)
def generate_report_task(self, session_id: int) -> dict:
    """Generate post-discussion feedback report using LLM workflow."""
    from workflows.report import run_report_workflow

    result = run_report_workflow(session_id)
    return {"session_id": session_id, "status": "completed", "result": result}
