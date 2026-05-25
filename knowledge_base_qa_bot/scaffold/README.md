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

Both folders require an OpenAI API key before running the server:

```bash
export OPENAI_API_KEY="sk-..."
```

Markdown KB uses the key for final answer generation. Vector RAG also uses it for embeddings.

Start with `markdown_kb` if you want the smallest dependency surface and the easiest debugging path.
