"""Celery application factory."""
from celery import Celery
from config import get_settings

settings = get_settings()

celery_app = Celery(
    "classroom",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["tasks.notifications"],
)

celery_app.conf.beat_schedule = {
    # Check assignment deadlines every hour
    "deadline-reminders": {
        "task": "tasks.notifications.send_deadline_reminders",
        "schedule": 3600.0,
    },
    # Auto-close classes whose ends_at has passed (every 30 minutes)
    "close-expired-classes": {
        "task": "tasks.notifications.close_expired_classes",
        "schedule": 1800.0,
    },
    # Clean up temp shared files daily
    "cleanup-shared-tmp": {
        "task": "tasks.notifications.cleanup_shared_tmp",
        "schedule": 86400.0,
    },
}

celery_app.conf.timezone = "Asia/Ho_Chi_Minh"
