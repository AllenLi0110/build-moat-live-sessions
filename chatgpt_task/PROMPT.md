# ChatGPT Task Scheduler Prototype

## System Requirements

Build a job scheduler with an MCP (Model Context Protocol) interface:
- Users schedule tasks for future execution via MCP tool calls
- A background watcher scans for due jobs and pushes them to a queue
- Workers pull jobs from the queue and execute them
- Support task creation, listing, status checking, and cancellation
- Tool naming follows namespace + action verb pattern (e.g., `task.create`)

### Architecture

```
User → MCP Tool Call → Job Scheduler API → DB
                                            ↓
                              Watcher (scans DB) → Queue → Worker (executes)
```

## Design Questions

Answer these before you start coding:

1. **Watcher vs Cron:** Why separate the watcher from the worker? What problems does a single cron job that both scans and executes have?

   Separate the watcher from the worker so job discovery and job execution can fail, scale, and retry independently. A single cron job that scans and executes couples two different workloads: if one long-running task blocks, the next scan is delayed; if execution crashes, due-job detection stops too. In this prototype, the watcher only finds due `pending` jobs and enqueues their IDs, while the worker owns execution and status updates.

2. **Queue Layer:** Why put a queue between the watcher and worker instead of having the watcher call the worker directly? What are the benefits?

   The queue decouples "this job is due" from "a worker is ready to run it." That gives the system buffering, backpressure, cleaner retries, and a path to multiple workers later. In this prototype, the in-memory `queue.Queue[int]` keeps the watcher fast: it marks jobs as `queued`, pushes job IDs, and returns to scanning instead of blocking on execution.

3. **Time Bucket Partitioning:** Instead of `SELECT * WHERE scheduled_at <= now()`, why partition jobs by time bucket (e.g., hour)? What happens to query performance at 1M+ jobs without partitioning?

   Time buckets reduce the search space for due-job scans. At 1M+ jobs, repeatedly scanning every row where `scheduled_at <= now()` becomes expensive because the database must evaluate a large historical set on every watcher pass. With hourly buckets, the watcher can use the `time_bucket` index to focus on due buckets, then apply `scheduled_at <= now()` and `status == "pending"` inside a much smaller candidate set.

4. **Tool Naming:** Why `task.create` instead of `createTask`? How does naming convention affect LLM tool selection accuracy?

   `task.create` exposes both the domain and the action in a predictable namespace-action form. LLMs choose tools more reliably when related tools share a namespace such as `task.list`, `task.status`, and `task.cancel`, because the names make the tool family and intent explicit. `createTask` is readable to humans but weaker as a scalable tool taxonomy.

5. **Registry vs If-Else:** Why use a dictionary registry to route tool calls instead of if-else chains? What happens when you need to add the 20th tool?

   A dictionary registry keeps routing declarative: tool names map directly to handler functions. Adding a new tool becomes adding one registry entry instead of editing a long branching function. By the 20th tool, if-else routing becomes harder to scan, easier to break, and harder to test; the registry keeps the MCP dispatch layer small and open to extension.

## Verification

Your prototype is a real MCP server. Test it with the MCP inspector — no Claude needed.

### 1. Start the server (sanity check)

```bash
python -m app.mcp_server
```

The process should hang waiting on stdin (it's a stdio MCP server — that's correct). Ctrl+C to stop. If you see an `ImportError` or other crash, fix that first.

### 2. Run the MCP inspector

Requires Node.js (uses `npx`).

```bash
npx @modelcontextprotocol/inspector python -m app.mcp_server
```

This opens a browser GUI (usually `http://localhost:5173`).

Steps in the GUI:

1. Click **Connect** -> should show 4 tools: `task.create`, `task.list`, `task.status`, `task.cancel`
2. **task.create** -> fill `description="Summarize tech news"`, `scheduled_at="2025-01-01T00:00:00"` (past time so watcher picks it up immediately) -> **Run Tool** -> response should include `{"job_id": 1, "status": "pending", ...}`
3. Wait ~10 seconds, then **task.status** -> `job_id: 1` -> status should now be `"completed"`
4. **task.create** with future time `"2099-12-31T00:00:00"` -> get `job_id: 2`
5. **task.cancel** -> `job_id: 2` -> status `"cancelled"`
6. **task.list** -> see all your jobs

### 3. (Optional) Connect to Claude Desktop / Claude Code

Once the inspector tests pass, the server is ready. To talk to it through Claude:

**Claude Desktop**: edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) and add (use absolute paths):

```json
{
  "mcpServers": {
    "task-scheduler": {
      "command": "/absolute/path/to/scaffold/.venv/bin/python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "/absolute/path/to/scaffold"
    }
  }
}
```

Restart Claude Desktop fully. The 🔨 icon in the chat input should show 4 tools.

**Claude Code**: edit `~/.claude.json` (top-level `mcpServers` for user scope) with the same block, or run `claude mcp add` from inside `scaffold/`.

Then chat:
> "Schedule a task to review PR #123 tomorrow at 9am."
> -> Claude calls `task.create` -> returns job_id
> "What's the status of that task?"
> -> Claude calls `task.status`

## Suggested Tech Stack

Python + the official `mcp` SDK is recommended (already in `requirements.txt` for the Guided Track). Challenge Track may use any language with an MCP SDK.
