"""MCP server for the task scheduler.

Run as a stdio MCP server:
    python -m app.mcp_server

Or test with the inspector:
    npx @modelcontextprotocol/inspector python -m app.mcp_server
"""

import asyncio
import json
from datetime import datetime

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine
from .models import Job
from .scheduler import get_time_bucket, start_scheduler


# ===================================================================
# Tool handlers — pure business logic, sync, take a DB Session
# ===================================================================


def handle_create_task(db: Session, *, description: str, scheduled_at: str) -> dict:
    """Create a new scheduled job."""
    dt = datetime.fromisoformat(scheduled_at)
    job = Job(
        description=description,
        scheduled_at=dt,
        time_bucket=get_time_bucket(dt),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return {"job_id": job.id, "status": job.status, "scheduled_at": str(job.scheduled_at)}


def handle_get_status(db: Session, *, job_id: int) -> dict:
    """Get the status of a scheduled job."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if job is None:
        return {"error": f"Job {job_id} not found"}
    return {
        "job_id": job.id,
        "description": job.description,
        "status": job.status,
        "scheduled_at": str(job.scheduled_at),
        "result": job.result,
    }


def handle_list_tasks(db: Session) -> dict:
    """List all scheduled jobs."""
    jobs = db.query(Job).order_by(Job.scheduled_at.desc()).all()
    return {
        "jobs": [
            {
                "job_id": j.id,
                "description": j.description,
                "status": j.status,
                "scheduled_at": str(j.scheduled_at),
            }
            for j in jobs
        ]
    }


def handle_cancel_task(db: Session, *, job_id: int) -> dict:
    """Cancel a scheduled job."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if job is None:
        return {"error": f"Job {job_id} not found"}
    if job.status in ("completed", "failed"):
        return {"error": f"Cannot cancel job in '{job.status}' state"}
    job.status = "cancelled"
    db.commit()
    return {"job_id": job.id, "status": "cancelled"}


# ===================================================================
# Tool definitions — what Claude / MCP client sees
# ===================================================================

TOOL_DEFINITIONS: list[Tool] = [
    Tool(
        name="task.create",
        description="Schedule a new task for future execution",
        inputSchema={
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "What the task should do",
                },
                "scheduled_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "When to run, ISO 8601 format (e.g. 2026-05-03T10:00:00)",
                },
            },
            "required": ["description", "scheduled_at"],
        },
    ),
    Tool(
        name="task.list",
        description="List all scheduled tasks",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="task.status",
        description="Get the status of a scheduled task by job_id",
        inputSchema={
            "type": "object",
            "properties": {
                "job_id": {"type": "integer", "description": "The job ID returned by task.create"},
            },
            "required": ["job_id"],
        },
    ),
    Tool(
        name="task.cancel",
        description="Cancel a scheduled task that hasn't completed yet",
        inputSchema={
            "type": "object",
            "properties": {
                "job_id": {"type": "integer", "description": "The job ID to cancel"},
            },
            "required": ["job_id"],
        },
    ),
]


# ===================================================================
# Registry pattern — name to handler dispatch
# ===================================================================

TOOL_REGISTRY = {
    "task.create": handle_create_task,
    "task.list": handle_list_tasks,
    "task.status": handle_get_status,
    "task.cancel": handle_cancel_task,
}


def route_tool_call(tool_name: str, arguments: dict, db: Session) -> dict:
    """Single dispatch point — look up handler in TOOL_REGISTRY and call it."""
    handler = TOOL_REGISTRY.get(tool_name)
    if handler is None:
        return {"error": f"Unknown tool: {tool_name}"}
    return handler(db, **arguments)


# ===================================================================
# MCP server wiring
# ===================================================================

server: Server = Server("task-scheduler")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOL_DEFINITIONS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Async wrapper — runs the sync handler in a thread to avoid blocking the event loop."""
    db = SessionLocal()
    try:
        result = await asyncio.to_thread(route_tool_call, name, arguments or {}, db)
    finally:
        db.close()
    return [TextContent(type="text", text=json.dumps(result, default=str, ensure_ascii=False))]


# ===================================================================
# Entry point — `python -m app.mcp_server`
# ===================================================================


async def main() -> None:
    Base.metadata.create_all(bind=engine)
    start_scheduler()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
