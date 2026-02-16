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


@celery_app.task(bind=True, time_limit=600)
def sync_integration_materials_task(
    self,
    job_id: int,
    provider: str,
    source_course_external_id: str,
    source_connection_id: int | None,
    target_course_id: int,
    target_session_id: int | None,
    actor_id: int | None,
    overwrite_title_prefix: str | None,
) -> dict:
    """Background task to sync materials from external LMS provider.

    This task handles the long-running sync operation including:
    1. Syncing sessions (Semanas) from external course
    2. Fetching and importing all materials
    3. Updating the IntegrationSyncJob record with progress
    """
    from datetime import datetime, timezone
    from api.core.database import SessionLocal
    from api.models.integration import IntegrationSyncJob
    from api.api.routes.integrations import (
        _resolve_provider,
        _sync_sessions_from_external,
        _import_materials_batch,
    )

    db = SessionLocal()
    try:
        # Update job status to running
        job = db.query(IntegrationSyncJob).filter(IntegrationSyncJob.id == job_id).first()
        if not job:
            return {"job_id": job_id, "status": "failed", "error": "Job not found"}

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        # Resolve provider
        p = _resolve_provider(provider, db=db, connection_id=source_connection_id, actor_user_id=actor_id)

        # Sync sessions first
        session_mapping = _sync_sessions_from_external(
            db=db,
            provider=provider,
            provider_obj=p,
            source_course_external_id=source_course_external_id,
            source_connection_id=source_connection_id,
            target_course_id=target_course_id,
        )

        # Fetch materials and build mapping
        materials = p.list_materials(source_course_external_id)
        material_session_map: dict[str, str] = {}
        for m in materials:
            if m.session_external_id:
                material_session_map[m.external_id] = m.session_external_id

        external_ids = [m.external_id for m in materials]
        job.requested_count = len(external_ids)
        db.commit()

        # Import materials
        result = _import_materials_batch(
            db=db,
            job=job,
            provider_name=provider,
            provider_obj=p,
            source_course_external_id=source_course_external_id,
            source_connection_id=source_connection_id,
            target_course_id=target_course_id,
            target_session_id=target_session_id,
            actor_id=actor_id,
            material_external_ids=external_ids,
            session_mapping=session_mapping,
            material_session_map=material_session_map,
            overwrite_title_prefix=overwrite_title_prefix,
        )

        # Update job completion
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        job.imported_count = result["imported_count"]
        job.skipped_count = result["skipped_count"]
        job.failed_count = result["failed_count"]
        db.commit()

        return {
            "job_id": job_id,
            "status": "completed",
            "imported_count": result["imported_count"],
            "skipped_count": result["skipped_count"],
            "failed_count": result["failed_count"],
        }

    except Exception as e:
        # Update job with error
        if job:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
        return {"job_id": job_id, "status": "failed", "error": str(e)}
    finally:
        db.close()


@celery_app.task(bind=True, time_limit=300)
def push_to_canvas_task(
    self,
    push_id: int,
    session_id: int,
    connection_id: int,
    external_course_id: str,
    push_type: str,
    custom_title: str | None = None,
) -> dict:
    """Push session summary to Canvas as announcement or assignment.

    This task:
    1. Gathers session content (posts, polls, etc.)
    2. Generates an LLM summary
    3. Creates the announcement/assignment in Canvas
    """
    from workflows.canvas_push import run_canvas_push_workflow

    result = run_canvas_push_workflow(
        push_id=push_id,
        session_id=session_id,
        connection_id=connection_id,
        external_course_id=external_course_id,
        push_type=push_type,
        custom_title=custom_title,
    )
    return result
