"""Celery tasks – deadline reminders and maintenance jobs."""
import os
import shutil
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, and_, update
from sqlalchemy.orm import Session

from tasks.celery_app import celery_app
from config import get_settings

settings = get_settings()

# We use a synchronous engine for Celery tasks (simpler than async in workers)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_engine = create_engine(settings.sync_database_url, pool_pre_ping=True)
SyncSession = sessionmaker(bind=_engine)


def _get_db() -> Session:
    return SyncSession()


@celery_app.task(name="tasks.notifications.send_deadline_reminders")
def send_deadline_reminders():
    """Create in-app notifications for assignments due within 24 hours."""
    from models import Assignment, Enrollment, Notification

    db = _get_db()
    try:
        now = datetime.now(tz=timezone.utc)
        window_end = now + timedelta(hours=24)

        # Assignments deadline within the next 24 hours
        upcoming = db.execute(
            select(Assignment).where(
                and_(
                    Assignment.deadline >= now,
                    Assignment.deadline <= window_end,
                )
            )
        ).scalars().all()

        created = 0
        for assignment in upcoming:
            # Get active enrollments for this class
            enrollments = db.execute(
                select(Enrollment).where(
                    Enrollment.class_id == assignment.class_id,
                    Enrollment.status == "active",
                )
            ).scalars().all()

            for enrollment in enrollments:
                # Avoid duplicate notifications (check last 25 hours)
                existing = db.execute(
                    select(Notification).where(
                        and_(
                            Notification.user_id == enrollment.user_id,
                            Notification.type == "deadline_reminder",
                            Notification.metadata_["assignment_id"].astext == str(assignment.id),
                            Notification.created_at >= now - timedelta(hours=25),
                        )
                    )
                ).scalar_one_or_none()
                if existing:
                    continue

                deadline_str = assignment.deadline.strftime("%H:%M %d/%m/%Y")
                db.add(Notification(
                    user_id=enrollment.user_id,
                    type="deadline_reminder",
                    title=f'Sắp hết hạn: {assignment.title}',
                    body=f'Bài tập sẽ hết hạn lúc {deadline_str}. Hãy nộp bài trước khi trễ hạn.',
                    metadata_={"assignment_id": str(assignment.id), "class_id": str(assignment.class_id)},
                ))
                created += 1

        db.commit()
        return f"Created {created} deadline reminder notifications"
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="tasks.notifications.close_expired_classes")
def close_expired_classes():
    """Automatically set class status to 'closed' when ends_at has passed."""
    from models import Class

    db = _get_db()
    try:
        now = datetime.now(tz=timezone.utc)
        result = db.execute(
            update(Class)
            .where(
                and_(
                    Class.ends_at < now,
                    Class.status == "active",
                )
            )
            .values(status="closed")
        )
        db.commit()
        return f"Closed {result.rowcount} expired classes"
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="tasks.notifications.cleanup_shared_tmp")
def cleanup_shared_tmp():
    """Remove shared_tmp files older than 7 days."""
    tmp_dir = os.path.join(settings.upload_dir, "shared_tmp")
    if not os.path.isdir(tmp_dir):
        return "shared_tmp directory not found"

    cutoff = datetime.now().timestamp() - 7 * 86400
    removed = 0
    for name in os.listdir(tmp_dir):
        path = os.path.join(tmp_dir, name)
        try:
            if os.path.getmtime(path) < cutoff:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                removed += 1
        except OSError:
            pass
    return f"Removed {removed} stale shared_tmp entries"
