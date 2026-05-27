# Guided Track Scaffolds

Choose one retrieval strategy:

```bash
# Recommended default
cd markdown_kb

# Traditional RAG comparison
cd vector_rag
```

Both folders expose the same API:

```text
GET /health
POST /index
POST /chat
```

Optionally set a Groq API key for final LLM answer generation:

```bash
export GROQ_API_KEY="gsk_..."
```

Both folders still run without `GROQ_API_KEY` by returning a local extractive fallback answer from retrieved context. Vector RAG uses local deterministic embeddings, so it does not require an embeddings API key.

Start with `markdown_kb` if you want the smallest dependency surface and the easiest debugging path.
