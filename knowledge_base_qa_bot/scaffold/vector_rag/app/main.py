from fastapi import FastAPI

from .indexer import load_vector_index
from .routes import router

app = FastAPI(title="Vector RAG Knowledge Base Q&A Bot")
app.include_router(router)


@app.on_event("startup")
def load_persisted_index():
    try:
        load_vector_index()
    except Exception as exc:
        print(f"[vector_rag] Skipping persisted FAISS load: {exc}", flush=True)
