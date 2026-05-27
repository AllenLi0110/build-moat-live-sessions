# AGENTS.md

# AWS Docs Knowledge Base Q&A Bot Prototype

This prototype is built on top of the Week 5 Knowledge Base Q&A Bot exercise.

Goal:

Build a grounded Q&A bot over a small Markdown knowledge base, then compare two retrieval strategies:

1. Markdown KB
2. Vector RAG

Extra highlight:

After answering, show what the retrieval result teaches us about the user's learning focus.

---

## Product Direction

This is not a general chatbot.

This is not trying to compete with GPT, Claude, or Gemini.

This is a retrieval strategy prototype that demonstrates:

- how Markdown KB retrieves structured sections
- how Vector RAG retrieves semantic chunks
- how retrieval unit affects the final answer
- how weak retrieval should be handled safely
- how Q&A interactions can become lightweight learning insights

---

## Course Alignment

The prototype must satisfy the course requirements:

- Read Markdown documents from `docs/`
- Build an index
- Expose `/health`
- Expose `/index`
- Expose `/chat`
- Ground answers in indexed documents
- Cite sources using `filename#heading`
- Refuse to answer when the knowledge base does not contain enough evidence

---

## Recommended Domain

Use a small AWS-related knowledge base.

Start with:

- Amazon SQS
- AWS Lambda with SQS
- Amazon EventBridge
- An anonymized personal implementation note about SQS / IoT / Queue Worker

Do not ingest the entire AWS documentation site.

Keep the dataset small enough to debug.

---

## Data Policy

Do not commit large copied AWS documentation content.

Use small curated Markdown files in `docs/`.

Each file should be readable and source-grounded.

If importing public documentation, preserve source links in frontmatter.

Example:

```md
---
title: "AWS Lambda with Amazon SQS"
source_url: "https://docs.aws.amazon.com/..."
source_type: "official_docs"
---

# AWS Lambda with Amazon SQS

...