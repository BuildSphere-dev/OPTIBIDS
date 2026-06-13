# backend/app/celery_app.py

"""
Celery application factory.

Broker  : Redis  (task queue)
Backend : Redis  (result storage)

Environment variables:
    REDIS_URL   — defaults to redis://localhost:6379/0
"""

import os
from celery import Celery
from celery.signals import worker_process_init

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery = Celery(
    "tender_app",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Retry failed tasks once after 60 seconds
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

# Auto-discover tasks in tasks.py
celery.autodiscover_tasks(["app"])


# Initialize database when worker starts
@worker_process_init.connect
def init_worker_db(**kwargs):
    """Initialize database tables on worker startup."""
    try:
        from .db import init_db
        print("▶  Initializing database for worker...")
        init_db()
        print(" Worker database initialized")
    except Exception as e:
        print(f" Failed to initialize worker database: {e}")

