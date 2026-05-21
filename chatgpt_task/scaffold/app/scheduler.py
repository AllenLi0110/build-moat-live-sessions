import logging
import queue
import threading
import time
from datetime import datetime

from sqlalchemy.orm import Session

from .database import SessionLocal
from .logging_utils import log_event
from .models import Job, _utcnow

# In-memory queue (simulates SQS for prototype)
job_queue: queue.Queue[int] = queue.Queue()
logger = logging.getLogger("task_scheduler.scheduler")

VALID_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"queued", "cancelled"},
    "queued": {"running", "cancelled"},
    "running": {"completed", "failed"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}


def transition_job_status(job: Job, new_status: str) -> tuple[bool, str | None]:
    """Apply a legal job status transition without committing the session."""
    allowed_statuses = VALID_STATUS_TRANSITIONS.get(job.status, set())
    if new_status not in allowed_statuses:
        return False, f"Cannot transition job from '{job.status}' to '{new_status}'"

    job.status = new_status
    return True, None


def get_time_bucket(scheduled_at: datetime) -> str:
    """Convert scheduled time to time bucket — used as DB partition key.

    The time bucket groups jobs into hourly windows so the watcher can
    efficiently query only the relevant partition instead of scanning
    the entire jobs table.
    """
    return scheduled_at.strftime("%Y%m%d%H")


def find_due_jobs(current_time: datetime, db: Session) -> list[Job]:
    """Watcher calls every minute: find due jobs in current time bucket.

    Queries the jobs table using the time bucket as a partition key,
    then filters for jobs that are due (scheduled_at <= now) and still
    in 'pending' status.
    """
    current_bucket = get_time_bucket(current_time)
    return (
        db.query(Job)
        .filter(
            Job.time_bucket <= current_bucket,
            Job.scheduled_at <= current_time,
            Job.status == "pending",
        )
        .order_by(Job.scheduled_at.asc())
        .all()
    )


def watcher_loop(interval: int = 10):
    """Watcher scans DB for due jobs and pushes them to the queue."""
    while True:
        db = SessionLocal()
        try:
            now = _utcnow()
            due_jobs = find_due_jobs(now, db)
            log_event(
                logger,
                "watcher.scan",
                current_time=now.isoformat(),
                current_bucket=get_time_bucket(now),
                due_job_count=len(due_jobs),
            )
            for job in due_jobs:
                transitioned, error = transition_job_status(job, "queued")
                if not transitioned:
                    log_event(
                        logger,
                        "watcher.skip_transition",
                        logging.WARNING,
                        job_id=job.id,
                        status=job.status,
                        reason=error,
                    )
                    continue
                db.commit()
                job_queue.put(job.id)
                log_event(
                    logger,
                    "watcher.enqueue",
                    job_id=job.id,
                    scheduled_at=job.scheduled_at.isoformat(),
                    queue_size=job_queue.qsize(),
                )
        except Exception as e:
            log_event(logger, "watcher.error", logging.ERROR, reason=str(e))
        finally:
            db.close()
        time.sleep(interval)


def worker_loop():
    """Worker pulls jobs from queue and executes them."""
    while True:
        job_id = job_queue.get()
        db = SessionLocal()
        job = None
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job is None:
                log_event(logger, "worker.skip_missing_job", logging.WARNING, job_id=job_id)
                continue
            if job.status == "cancelled":
                log_event(logger, "worker.skip_cancelled_job", job_id=job_id)
                continue

            transitioned, error = transition_job_status(job, "running")
            if not transitioned:
                log_event(
                    logger,
                    "worker.skip_transition",
                    logging.WARNING,
                    job_id=job.id,
                    status=job.status,
                    target_status="running",
                    reason=error,
                )
                continue
            db.commit()
            log_event(logger, "worker.execute", job_id=job.id)

            # Simulate execution — in production this would call LLM
            job.result = f"Executed: {job.description}"
            transitioned, error = transition_job_status(job, "completed")
            if not transitioned:
                log_event(
                    logger,
                    "worker.skip_transition",
                    logging.WARNING,
                    job_id=job.id,
                    status=job.status,
                    target_status="completed",
                    reason=error,
                )
                continue
            db.commit()
            log_event(logger, "worker.complete", job_id=job.id)
        except Exception as e:
            if job is not None:
                transitioned, error = transition_job_status(job, "failed")
                if transitioned:
                    job.result = str(e)
                    db.commit()
                    log_event(
                        logger,
                        "worker.fail",
                        logging.ERROR,
                        job_id=job.id,
                        reason=str(e),
                    )
                else:
                    log_event(
                        logger,
                        "worker.fail_transition",
                        logging.ERROR,
                        job_id=job.id,
                        status=job.status,
                        reason=error,
                        original_error=str(e),
                    )
            else:
                log_event(logger, "worker.error", logging.ERROR, job_id=job_id, reason=str(e))
        finally:
            db.close()
            job_queue.task_done()


def start_scheduler():
    """Start watcher and worker threads."""
    watcher = threading.Thread(target=watcher_loop, daemon=True)
    worker = threading.Thread(target=worker_loop, daemon=True)
    watcher.start()
    worker.start()
    log_event(logger, "scheduler.started")
