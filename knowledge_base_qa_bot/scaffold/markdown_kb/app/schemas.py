from pydantic import BaseModel


class IndexResponse(BaseModel):
    files_indexed: int
    sections_indexed: int


class DocumentSection(BaseModel):
    source: str
    heading: str


class DocumentInfo(BaseModel):
    file: str
    sections: list[DocumentSection]


class DocumentsResponse(BaseModel):
    files_indexed: int
    sections_indexed: int
    documents: list[DocumentInfo]


class ChatRequest(BaseModel):
    query: str


class SourceInfo(BaseModel):
    source: str
    heading: str
    score: float
    content: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceInfo]
    learning_focus: str = ""
