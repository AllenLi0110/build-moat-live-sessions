from fastapi import APIRouter

from . import indexer
from .retrieval import query
from .schemas import ChatRequest, ChatResponse, DocumentsResponse, IndexResponse

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/index", response_model=IndexResponse)
def index_docs():
    files_count, sections_count = indexer.build_index()
    return IndexResponse(files_indexed=files_count, sections_indexed=sections_count)


@router.get("/documents", response_model=DocumentsResponse)
def documents():
    return DocumentsResponse(
        files_indexed=indexer.files_indexed,
        sections_indexed=len(indexer.sections),
        documents=indexer.list_documents(),
    )


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    return query(req.query)
