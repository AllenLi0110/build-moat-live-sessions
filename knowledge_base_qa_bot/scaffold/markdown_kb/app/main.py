from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from dotenv import load_dotenv

from .indexer import build_index, load_index_json
from .routes import router

APP_DIR = Path(__file__).resolve().parent
PROJECT_DIR = APP_DIR.parent
load_dotenv(PROJECT_DIR / ".env")

app = FastAPI(title="Markdown Knowledge Base Q&A Bot")
app.include_router(router)

STATIC_DIR = APP_DIR / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def browser_ui():
    return FileResponse(STATIC_DIR / "index.html")


@app.on_event("startup")
def load_persisted_index():
    _, sections_count = load_index_json()
    if sections_count == 0:
        build_index()
