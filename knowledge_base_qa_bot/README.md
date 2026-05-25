# Knowledge Base Q&A Bot

## How to Use

1. Read `PROMPT.md`
2. Review the sample Markdown docs in `docs/`
3. Choose a learning mode:
   - **Challenge Track:** Build from scratch using `PROMPT.md` as your spec
   - **Guided Track:** Pick a scaffold and fill in the TODOs
4. Choose a retrieval strategy:
   - **Markdown KB:** Markdown section index + BM25 keyword search
   - **Vector RAG:** Markdown chunks + embeddings + vector search
5. Verify with the curl tests in `PROMPT.md`
6. Bring your design tradeoffs to live session

## Recommended Path

If you want the simplest guided path, start here:

```bash
cd scaffold/markdown_kb
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then run the verification tests from `PROMPT.md`.

## Guided Track Options

| Strategy | Folder | Core Idea | Best For |
|----------|--------|-----------|----------|
| Markdown KB | `scaffold/markdown_kb/` | Parse Markdown headings, build section-level index, rank sections with BM25 | Small knowledge bases, agent-readable docs, easy debugging |
| Vector RAG | `scaffold/vector_rag/` | Split Markdown into chunks, embed chunks, retrieve with vector search | Larger corpora, semantic queries, traditional RAG practice |

## Shared API

Both strategies should expose the same API:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness check |
| POST | `/index` | Read `docs/*.md` and build the retrieval index |
| POST | `/chat` | Answer a question with grounded sources |

After calling `/index`, each strategy persists its retrieval index:

| Strategy | Persisted Index | Startup Behavior |
|----------|-----------------|------------------|
| Markdown KB | `.kb/index.json` | Loads the section index into memory |
| Vector RAG | `.kb/faiss_index/` | Loads the FAISS index into memory |

Restarting the server should not require rebuilding immediately. Re-run `/index` after changing `docs/*.md`.

## Prerequisites

Both guided tracks use OpenAI for final answer generation:

```bash
export OPENAI_API_KEY="sk-..."
```

The Markdown KB track does not need embeddings. The Vector RAG track uses OpenAI embeddings.

## Stretch Goals

Pick one or more after the core `/index` and `/chat` flow works.

### Score Threshold and Fallback

Add a similarity or BM25 score threshold so weak retrieval results become an explicit fallback instead of a shaky answer. Track how often the system says it cannot confirm from the knowledge base.

### Streaming Interface

For a better user experience, add a streaming endpoint:

```text
POST /chat/stream
```

Recommended approach:

- Use Server-Sent Events (SSE) for a simple one-way token stream
- Send `source` events before token events so the UI can show what context was selected
- Send `token` events as the LLM produces output
- Send a final `done` event when the answer is complete

This is intentionally a stretch goal. The core exercise is still retrieval quality and grounded answer generation.

### Browser UI

Build a tiny browser UI over `/chat` or `/chat/stream`. Show selected sources before the answer, then render streamed tokens as they arrive.

### Multi-Format Import

Karpathy-style knowledge bases often treat Markdown as the canonical knowledge format, not the only input format.

Add an import pipeline:

```text
raw/*.txt or raw/*.html -> docs/*.md -> POST /index -> retrieval index
```

Recommended scope:

- Start with `.txt` and `.html`
- Preserve source filename in front matter or metadata
- Convert headings into Markdown headings
- Keep `docs/*.md` as the human-readable canonical copy
- Rebuild the retrieval index after conversion

Avoid parsing complex PDFs or spreadsheets first. The goal is to teach normalization into clean Markdown, not file parser edge cases.

### Alternative Interfaces

Keep the retrieval logic the same, but expose it through another interface:

```text
CLI: kb index / kb ask
MCP: expose index, search, and chat as agent tools
Web UI: simple chat screen over /chat or /chat/stream
```

This is useful for comparing interface design. The core exercise should still stay focused on indexing, retrieval, grounding, and citation quality.

### Wiki Index Generation

Generate `wiki/index.md` from `.kb/index.json` so humans and agents can browse the available topics without calling the API.

### Answer Filing

Write useful Q&A results back into `wiki/` after review. Keep filed answers source-grounded and preserve citations back to the original Markdown sections.

### Conversation Memory

Add short conversation memory for follow-up questions. Memory should help interpret the query, but it must not override retrieved sources or citation requirements.

### Paraphrase Comparison

Create a small set of paraphrased queries and compare Markdown KB vs Vector RAG. Look for cases where BM25 misses synonyms and cases where vector search retrieves semantically related but wrong chunks.
