# AGENTS.md — ChatGPT Task Scheduler Prototype

## Goal

Build the guided-track ChatGPT Task Scheduler prototype in the existing `scaffold/` directory, using `PROMPT.md` as the specification.

The result must be a real stdio MCP server that lets users schedule, list, inspect, and cancel tasks through MCP tool calls.

Required MCP tools:

- `task.create`
- `task.list`
- `task.status`
- `task.cancel`

Target architecture:

```text
User -> MCP Tool Call -> Job Scheduler API -> DB
                                           |
                                           v
                              Watcher -> Queue -> Worker
```

## Source Of Truth

`PROMPT.md` is the product and exercise specification.

Use `README.md` for setup and guided-track orientation, but do not treat it as overriding `PROMPT.md`.

This `AGENTS.md` defines how Codex should execute the task, what boundaries to preserve, and how to verify completion.

If `PROMPT.md` and this file conflict, follow `PROMPT.md` for product behavior and this file for execution workflow.

## Required Workflow

Follow this order strictly:

1. Read `PROMPT.md`, `README.md`, and this `AGENTS.md`.
2. Answer the five Design Questions directly in `PROMPT.md` before implementation.
3. Inspect the guided scaffold under `scaffold/app/`.
4. Implement only the required TODOs.
5. Run the MCP server sanity check from `scaffold/`.
6. Verify the full flow with the MCP inspector.
7. Fix failures by reading actual error output and correcting the root cause.

Do not mark the task complete until the MCP inspector flow works.

## Design Questions

Before coding, write clear answers in `PROMPT.md` for these questions:

1. Watcher vs Cron: why keep scanning separate from execution?
2. Queue Layer: why place a queue between watcher and worker?
3. Time Bucket Partitioning: why query by time bucket instead of scanning all due jobs?
4. Tool Naming: why use `task.create` instead of `createTask`?
5. Registry vs If-Else: why route tools through a dictionary registry?

Keep the answers concise but technically defensible. They should explain the engineering tradeoff, not just restate the implementation.

Each answer should connect the concept back to this prototype's implementation.
Each answer should connect the concept back to this prototype's implementation.

## Files To Modify

Primary implementation files:

- `scaffold/app/scheduler.py`
- `scaffold/app/mcp_server.py`

Expected TODOs:

- `get_time_bucket()`
- `find_due_jobs()`
- `TOOL_REGISTRY`
- `route_tool_call()`

Only modify other files when a runtime error, test, or MCP inspector verification requires it.

Tests may be added under `scaffold/tests/` if needed for local verification.

Do not create a parallel implementation outside `scaffold/`.

Do not rewrite scaffold boilerplate unless there is a concrete failure.

## Architecture Contract

### Watcher

The watcher scans the database for jobs that are due.

It is responsible for:

- computing the current time
- finding pending due jobs
- marking due jobs as `queued`
- pushing job IDs into the queue

The watcher must not execute task work directly.

Use the scaffold's existing polling interval unless a verification failure requires changing it.

### Queue

The queue decouples job discovery from job execution.

For this prototype, keep the existing in-memory `queue.Queue[int]`.

Queue items should be job IDs, not SQLAlchemy model instances.

Do not introduce Redis, Celery, SQS, RabbitMQ, or any external queue system.

### Worker

The worker pulls job IDs from the queue and executes them.

The worker should load the job from the database by ID before executing it.

Cancelled or missing jobs must not be executed.

For this prototype, execution is simulated by setting:

```python
job.result = f"Executed: {job.description}"
job.status = "completed"
```

Do not connect a real LLM unless explicitly requested.

Connecting this MCP server to Claude Desktop is in scope.

Claude Desktop should act as the MCP client that calls `task.create`, `task.list`, `task.status`, and `task.cancel`.

The worker itself should still use simulated execution unless the user explicitly requests a separate LLM execution feature.

### MCP Router

The MCP server must route tool calls through a dictionary registry.

Do not implement routing with a long `if` / `elif` chain.

The async MCP wrapper should remain thin. Business logic should stay in sync handler functions that receive a SQLAlchemy `Session`.

Every tool listed in `TOOL_DEFINITIONS` must have a matching entry in `TOOL_REGISTRY`.

## Implementation Requirements

### Time Buckets

`get_time_bucket(scheduled_at)` must return an hourly bucket string in this format:

```text
YYYYMMDDHH
```

Example:

```text
2026051413
```

Use `datetime.strftime("%Y%m%d%H")`.

### Finding Due Jobs

`find_due_jobs(current_time, db)` must return only jobs that satisfy all of these:

- `Job.time_bucket <= get_time_bucket(current_time)`
- `Job.scheduled_at <= current_time`
- `Job.status == "pending"`

The bucket comparison must include earlier buckets so tasks scheduled in the past are picked up immediately during inspector and Claude Desktop demos.

The query should use the existing SQLAlchemy model and return a list of `Job` objects.

### Tool Registry

`TOOL_REGISTRY` must map MCP tool names to handler functions:

```python
TOOL_REGISTRY = {
    "task.create": handle_create_task,
    "task.list": handle_list_tasks,
    "task.status": handle_get_status,
    "task.cancel": handle_cancel_task,
}
```

Tool names must exactly match the names in `TOOL_DEFINITIONS`.

Do not rename tools.

### Tool Routing

`route_tool_call(tool_name, arguments, db)` must:

1. Look up the handler in `TOOL_REGISTRY`.
2. Return `{"error": f"Unknown tool: {tool_name}"}` if the tool is not registered.
3. Call the handler with `db` and `**arguments`.
4. Return the handler result.

All tool results must be JSON-serializable dictionaries.

## Testing And Verification

Run all commands from:

```bash
cd chatgpt_task/scaffold
```

Set up the Python environment if needed:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Sanity check:

```bash
python -m app.mcp_server
```

Expected behavior: the process stays running and waits on stdin. This is correct for a stdio MCP server.

If the server crashes with an `ImportError`, SQLAlchemy error, MCP error, or traceback, fix that before running the inspector.

Inspector verification:

```bash
npx @modelcontextprotocol/inspector python -m app.mcp_server
```

The inspector must show exactly these four tools:

- `task.create`
- `task.list`
- `task.status`
- `task.cancel`

Manual inspector flow:

1. Run `task.create` with `description="Summarize tech news"` and a past `scheduled_at`.
2. Confirm the response includes a `job_id` and `status`.
3. Wait about 10 seconds.
4. Run `task.status` for that `job_id`.
5. Confirm the status becomes `completed`.
6. Run `task.create` with a future `scheduled_at`.
7. Run `task.cancel` for the future job.
8. Confirm the response status is `cancelled`.
9. Run `task.list` and confirm both jobs are visible.

## Feedback Loop

When verification fails:

1. Read the full error output.
2. Identify the failing layer: import, DB, scheduler, queue, worker, MCP discovery, or tool routing.
3. Fix only the failing path.
4. Re-run the same verification step.

Do not guess.

Do not skip or weaken verification to make the task appear complete.

## Non-Goals

Do not add these unless explicitly requested:

| Item | Reason |
|---|---|
| FastAPI or HTTP API | The required interface is MCP over stdio |
| Frontend UI | The inspector is the required UI for verification |
| Authentication | Out of scope for the prototype |
| Redis, Celery, SQS, RabbitMQ | The scaffold specifies an in-memory queue |
| Real LLM execution | Worker execution is simulated in this exercise |
| Recurring jobs | Listed only as a bonus challenge |
| Job chaining | Listed only as a bonus challenge |
| Alembic migrations | `Base.metadata.create_all` is sufficient for the prototype |
| Multi-database support | SQLite is the scaffold target |

## Definition Of Done

The task is complete only when all of these are true:

- [ ] The five Design Questions in `PROMPT.md` have clear written answers.
- [ ] `get_time_bucket()` returns hourly bucket strings in `YYYYMMDDHH` format.
- [ ] `find_due_jobs()` returns only pending jobs due in the current or earlier time buckets.
- [ ] `TOOL_REGISTRY` contains all four required MCP tools.
- [ ] `route_tool_call()` dispatches through `TOOL_REGISTRY`.
- [ ] Unknown tools return `{"error": f"Unknown tool: {tool_name}"}`.
- [ ] `python -m app.mcp_server` starts without crashing.
- [ ] MCP inspector connects successfully.
- [ ] MCP inspector shows `task.create`, `task.list`, `task.status`, and `task.cancel`.
- [ ] A past scheduled task is picked up by the watcher and completed by the worker.
- [ ] A future scheduled task can be cancelled.
- [ ] `task.list` shows created jobs with their statuses.


請列出目前 task scheduler 裡的所有任務