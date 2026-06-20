"""
Celery application instance configured from app settings.
"""

from celery import Celery
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "transaction_pipeline",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task settings
    task_track_started=True,
    task_acks_late=True,           # ack after task completes (reliability)
    worker_prefetch_multiplier=1,  # one task at a time per worker
    task_reject_on_worker_lost=True,

    # Result expiry
    result_expires=3600,  # 1 hour

    # Task routes removed to use default queue

    # Rate limiting
    # Imports
    include=["app.tasks"],
    
    # Eager mode (for local dev without Redis)
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
)
