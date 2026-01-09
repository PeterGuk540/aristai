import os
from celery import Celery

# Read Redis URL from environment
# Default uses docker-compose service name; for local dev use: redis://localhost:6379/0
redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "aristai_worker",
    broker=redis_url,
    backend=redis_url,  # Required for task status/result retrieval
    include=["worker.tasks"],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes max per task
    worker_prefetch_multiplier=1,  # Fair task distribution
)
