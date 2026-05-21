from datetime import datetime, timedelta
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.mcp_server import TOOL_DEFINITIONS, route_tool_call
from app.models import Job
from app.scheduler import find_due_jobs, get_time_bucket, transition_job_status


class SchedulerTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine)

    def test_get_time_bucket_uses_hourly_format(self):
        scheduled_at = datetime(2026, 5, 14, 13, 45, 30)

        self.assertEqual(get_time_bucket(scheduled_at), "2026051413")

    def test_find_due_jobs_returns_pending_jobs_in_due_buckets(self):
        db = self.Session()
        now = datetime(2026, 5, 14, 13, 0, 0)
        past = now - timedelta(hours=1)
        future = now + timedelta(hours=1)
        try:
            due_job = Job(
                description="due",
                scheduled_at=past,
                time_bucket=get_time_bucket(past),
                status="pending",
            )
            future_job = Job(
                description="future",
                scheduled_at=future,
                time_bucket=get_time_bucket(future),
                status="pending",
            )
            completed_job = Job(
                description="completed",
                scheduled_at=past,
                time_bucket=get_time_bucket(past),
                status="completed",
            )
            db.add_all([due_job, future_job, completed_job])
            db.commit()

            jobs = find_due_jobs(now, db)

            self.assertEqual([job.description for job in jobs], ["due"])
        finally:
            db.close()

    def test_route_tool_call_uses_registry(self):
        db = self.Session()
        try:
            result = route_tool_call(
                "task_create",
                {"description": "demo", "scheduled_at": "2026-05-14T13:00:00"},
                db,
            )

            self.assertEqual(result["status"], "pending")
            self.assertEqual(result["job_id"], 1)
        finally:
            db.close()

    def test_create_task_normalizes_timezone_aware_datetime_to_utc(self):
        db = self.Session()
        try:
            result = route_tool_call(
                "task_create",
                {"description": "demo", "scheduled_at": "2026-05-14T17:55:00+08:00"},
                db,
            )
            job = db.query(Job).filter(Job.id == result["job_id"]).first()

            self.assertEqual(job.scheduled_at, datetime(2026, 5, 14, 9, 55, 0))
            self.assertEqual(job.time_bucket, "2026051409")
        finally:
            db.close()

    def test_create_task_defaults_naive_datetime_to_taiwan_timezone(self):
        db = self.Session()
        try:
            result = route_tool_call(
                "task_create",
                {"description": "demo", "scheduled_at": "2026-05-14T17:55:00"},
                db,
            )
            job = db.query(Job).filter(Job.id == result["job_id"]).first()

            self.assertEqual(job.scheduled_at, datetime(2026, 5, 14, 9, 55, 0))
            self.assertEqual(job.time_bucket, "2026051409")
        finally:
            db.close()

    def test_task_responses_display_scheduled_at_in_taiwan_timezone(self):
        db = self.Session()
        try:
            created = route_tool_call(
                "task_create",
                {"description": "demo", "scheduled_at": "2026-05-14T17:55:00"},
                db,
            )
            status = route_tool_call("task_status", {"job_id": created["job_id"]}, db)
            listed = route_tool_call("task_list", {}, db)

            self.assertEqual(created["scheduled_at"], "2026-05-14 17:55:00+08:00")
            self.assertEqual(status["scheduled_at"], "2026-05-14 17:55:00+08:00")
            self.assertEqual(
                listed["jobs"][0]["scheduled_at"],
                "2026-05-14 17:55:00+08:00",
            )
        finally:
            db.close()

    def test_create_task_returns_error_for_invalid_scheduled_at(self):
        db = self.Session()
        try:
            result = route_tool_call(
                "task_create",
                {"description": "demo", "scheduled_at": "not-a-date"},
                db,
            )

            self.assertEqual(result, {"error": "scheduled_at must be ISO 8601 datetime"})
            self.assertEqual(db.query(Job).count(), 0)
        finally:
            db.close()

    def test_create_task_returns_error_for_empty_description(self):
        db = self.Session()
        try:
            result = route_tool_call(
                "task_create",
                {"description": "  ", "scheduled_at": "2026-05-14T13:00:00"},
                db,
            )

            self.assertEqual(result, {"error": "description must be a non-empty string"})
            self.assertEqual(db.query(Job).count(), 0)
        finally:
            db.close()

    def test_route_tool_call_keeps_dot_name_alias(self):
        db = self.Session()
        try:
            result = route_tool_call(
                "task.create",
                {"description": "demo", "scheduled_at": "2026-05-14T13:00:00"},
                db,
            )

            self.assertEqual(result["status"], "pending")
            self.assertEqual(result["job_id"], 1)
        finally:
            db.close()

    def test_exposed_tool_names_are_claude_compatible(self):
        tool_names = [tool.name for tool in TOOL_DEFINITIONS]

        self.assertEqual(tool_names, ["task_create", "task_list", "task_status", "task_cancel"])

    def test_route_tool_call_returns_unknown_tool_error(self):
        db = self.Session()
        try:
            result = route_tool_call("task.missing", {}, db)

            self.assertEqual(result, {"error": "Unknown tool: task.missing"})
        finally:
            db.close()

    def test_transition_job_status_allows_legal_transition(self):
        job = Job(status="pending")

        transitioned, error = transition_job_status(job, "queued")

        self.assertTrue(transitioned)
        self.assertIsNone(error)
        self.assertEqual(job.status, "queued")

    def test_transition_job_status_rejects_illegal_transition(self):
        job = Job(status="running")

        transitioned, error = transition_job_status(job, "cancelled")

        self.assertFalse(transitioned)
        self.assertEqual(error, "Cannot transition job from 'running' to 'cancelled'")
        self.assertEqual(job.status, "running")

    def test_cancel_task_rejects_running_job(self):
        db = self.Session()
        try:
            scheduled_at = datetime(2026, 5, 14, 13, 0, 0)
            job = Job(
                description="running",
                scheduled_at=scheduled_at,
                time_bucket=get_time_bucket(scheduled_at),
                status="running",
            )
            db.add(job)
            db.commit()

            result = route_tool_call("task_cancel", {"job_id": job.id}, db)

            self.assertEqual(
                result,
                {"error": "Cannot transition job from 'running' to 'cancelled'"},
            )
            self.assertEqual(job.status, "running")
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
