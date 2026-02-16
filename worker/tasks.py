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


# ============ Enhanced AI Features Tasks ============

@celery_app.task(bind=True, time_limit=300)
def generate_live_summary_task(self, session_id: int) -> dict:
    """Generate a live discussion summary for a session."""
    from workflows.enhanced_features import generate_live_summary

    result = generate_live_summary(session_id)
    return {"session_id": session_id, "status": "completed", "result": result}


@celery_app.task(bind=True, time_limit=300)
def generate_student_groups_task(
    self,
    session_id: int,
    group_type: str = "mixed_participation",
    num_groups: int = 4,
    topics: list | None = None,
) -> dict:
    """Generate AI-powered student groups for a session."""
    from workflows.enhanced_features import generate_student_groups

    result = generate_student_groups(
        session_id=session_id,
        group_type=group_type,
        num_groups=num_groups,
        topics=topics,
    )
    return {"session_id": session_id, "status": "completed", "result": result}


@celery_app.task(bind=True, time_limit=600)
def generate_followups_task(
    self,
    session_id: int,
    student_ids: list | None = None,
) -> dict:
    """Generate personalized follow-up messages for students."""
    from workflows.enhanced_features import generate_followups

    result = generate_followups(
        session_id=session_id,
        student_ids=student_ids,
    )
    return {"session_id": session_id, "status": "completed", "result": result}


@celery_app.task(bind=True, time_limit=300)
def generate_questions_task(
    self,
    session_id: int,
    question_types: list | None = None,
    num_questions: int = 5,
    difficulty: str | None = None,
) -> dict:
    """Generate quiz questions from session discussion."""
    from workflows.enhanced_features import generate_questions

    if question_types is None:
        question_types = ["mcq", "short_answer"]

    result = generate_questions(
        session_id=session_id,
        question_types=question_types,
        num_questions=num_questions,
        difficulty=difficulty,
    )
    return {"session_id": session_id, "status": "completed", "result": result}


@celery_app.task(bind=True, time_limit=600)
def analyze_participation_task(self, course_id: int) -> dict:
    """Analyze participation metrics for a course."""
    from workflows.enhanced_features import analyze_participation

    result = analyze_participation(course_id)
    return {"course_id": course_id, "status": "completed", "result": result}


@celery_app.task(bind=True, time_limit=300)
def generate_ai_assistant_response_task(
    self,
    session_id: int,
    student_id: int,
    question: str,
    post_id: int | None = None,
) -> dict:
    """Generate AI teaching assistant response to a student question."""
    from workflows.enhanced_features import generate_ai_assistant_response

    result = generate_ai_assistant_response(
        session_id=session_id,
        student_id=student_id,
        question=question,
        post_id=post_id,
    )
    return {"session_id": session_id, "status": "completed", "result": result}


@celery_app.task(bind=True, time_limit=1800)
def transcribe_recording_task(self, recording_id: int) -> dict:
    """Transcribe and analyze a session recording."""
    from workflows.enhanced_features import transcribe_recording

    result = transcribe_recording(recording_id)
    return {"recording_id": recording_id, "status": "completed", "result": result}


@celery_app.task(bind=True, time_limit=600)
def analyze_objective_coverage_task(self, course_id: int) -> dict:
    """Analyze learning objective coverage for a course."""
    from workflows.enhanced_features import analyze_objective_coverage

    result = analyze_objective_coverage(course_id)
    return {"course_id": course_id, "status": "completed", "result": result}


@celery_app.task(bind=True, time_limit=300)
def create_peer_review_assignments_task(
    self,
    session_id: int,
    submission_post_ids: list | None = None,
    reviews_per_submission: int = 2,
) -> dict:
    """Create AI-matched peer review assignments."""
    from workflows.enhanced_features import create_peer_review_assignments

    result = create_peer_review_assignments(
        session_id=session_id,
        submission_post_ids=submission_post_ids,
        reviews_per_submission=reviews_per_submission,
    )
    return {"session_id": session_id, "status": "completed", "result": result}


@celery_app.task(bind=True, time_limit=120)
def translate_post_task(self, post_id: int, target_language: str) -> dict:
    """Translate a single post to a target language."""
    from workflows.enhanced_features import translate_post

    result = translate_post(post_id, target_language)
    return {"post_id": post_id, "status": "completed", "result": result}


@celery_app.task(bind=True, time_limit=1800)
def translate_session_posts_task(self, session_id: int, target_language: str) -> dict:
    """Translate all posts in a session to a target language."""
    from workflows.enhanced_features import translate_session_posts

    result = translate_session_posts(session_id, target_language)
    return {"session_id": session_id, "status": "completed", "result": result}
