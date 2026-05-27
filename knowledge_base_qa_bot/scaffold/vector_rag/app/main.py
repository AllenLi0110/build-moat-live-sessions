from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from dotenv import load_dotenv

from .indexer import build_index, load_vector_index
from .routes import router

PROJECT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_DIR / ".env")

app = FastAPI(title="Vector RAG Knowledge Base Q&A Bot")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.on_event("startup")
def load_persisted_index():
    try:
        _, chunks_count = load_vector_index()
        if chunks_count == 0:
            build_index()
    except Exception as exc:
        print(f"[vector_rag] Rebuilding FAISS index after load failure: {exc}", flush=True)
        build_index()
