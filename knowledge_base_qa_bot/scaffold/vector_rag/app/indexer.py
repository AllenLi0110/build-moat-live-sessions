import hashlib
import json
import math
import os
import re
import shutil
from pathlib import Path
from typing import Optional

from langchain.schema import Document
from langchain_core.embeddings import Embeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter

# FAISS can conflict with another libomp loaded by the macOS Python runtime.
# Set this before importing the FAISS wrapper so persisted index reload works.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
from langchain_community.vectorstores import FAISS


DOCS_DIR = Path(__file__).resolve().parents[3] / "docs"
INDEX_DIR = Path(__file__).resolve().parents[3] / ".kb" / "faiss_index"
EMBEDDING_MODEL = "local-hash-embeddings-v1"
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
TOKEN_RE = re.compile(r"[a-z0-9]+")
SYNONYMS = {
    "back": ["refund"],
    "how": ["timeline"],
    "long": ["timeline"],
    "money": ["refund"],
    "receive": ["processed"],
    "received": ["processed"],
    "take": ["processed", "timeline"],
    "takes": ["processed", "timeline"],
    "will": ["timeline"],
}

# TODO: Configure chunking parameters for traditional RAG.
#
# Design decision: Balance semantic recall against context noise.
#
# Hints:
# 1. chunk_size around 500 chars is a reasonable prototype default.
# 2. chunk_overlap helps avoid cutting facts at boundaries.
# 3. separators should prefer Markdown structure before individual words.
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=80,
    separators=["\n\n", "\n", ". ", " "],
)

vectorstore: Optional[FAISS] = None
_embeddings = None
files_indexed = 0
sections_indexed = 0


class HashEmbeddings(Embeddings):
    """Small deterministic embedding model for local FAISS retrieval."""

    dimension = 256

    def _vectorize(self, text: str) -> list[float]:
        tokens = []
        for token in TOKEN_RE.findall(text.lower()):
            tokens.append(token)
            tokens.extend(SYNONYMS.get(token, []))

        vector = [0.0] * self.dimension

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for offset in range(0, 16, 2):
                bucket = int.from_bytes(digest[offset : offset + 2], "big") % self.dimension
                vector[bucket] += 1.0 if offset < 8 else 0.5

        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vectorize(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vectorize(text)


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"


def get_embeddings():
    global _embeddings

    if _embeddings is None:
        _embeddings = HashEmbeddings()

    return _embeddings


def embedding_dimension(embeddings: Optional[Embeddings] = None) -> int:
    if embeddings is None:
        embeddings = get_embeddings()

    return len(embeddings.embed_query("dimension check"))


def load_markdown_sections(path: Path) -> list[Document]:
    documents: list[Document] = []
    heading_stack: list[tuple[int, str]] = []
    current_heading: str | None = None
    current_path: list[str] = []
    current_lines: list[str] = []

    def flush_section() -> None:
        if current_heading is None:
            return

        content = "\n".join(current_lines).strip()
        if not content:
            return

        heading_path = " > ".join(current_path)
        source = f"{path.name}#{slugify(current_heading)}"
        documents.append(
            Document(
                page_content=f"Heading: {heading_path}\n\n{content}",
                metadata={
                    "source": source,
                    "file": path.name,
                    "heading": heading_path,
                },
            )
        )

    for line in path.read_text(encoding="utf-8").splitlines():
        match = HEADING_RE.match(line)
        if match:
            flush_section()
            level = len(match.group(1))
            heading = match.group(2).strip()
            heading_stack = [
                (stack_level, stack_heading)
                for stack_level, stack_heading in heading_stack
                if stack_level < level
            ]
            heading_stack.append((level, heading))
            current_heading = heading
            current_path = [stack_heading for _, stack_heading in heading_stack]
            current_lines = []
            continue

        current_lines.append(line)

    flush_section()
    return documents


def build_index(docs_dir: Path = DOCS_DIR) -> tuple[int, int]:
    global vectorstore, files_indexed, sections_indexed

    section_docs: list[Document] = []
    for path in sorted(docs_dir.glob("*.md")):
        section_docs.extend(load_markdown_sections(path))

    files_indexed = len({doc.metadata["file"] for doc in section_docs})
    chunks = splitter.split_documents(section_docs)
    sections_indexed = len(chunks)

    if not chunks:
        vectorstore = None
    else:
        vectorstore = FAISS.from_documents(chunks, get_embeddings())

    save_vector_index()
    return files_indexed, sections_indexed


def save_vector_index(index_dir: Optional[Path] = None) -> None:
    if index_dir is None:
        index_dir = INDEX_DIR

    if vectorstore is None:
        if index_dir.exists():
            shutil.rmtree(index_dir)
        return

    index_dir.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(index_dir))
    stale_records_file = index_dir / "chunks.json"
    if stale_records_file.exists():
        stale_records_file.unlink()

    metadata = {
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dimension": embedding_dimension(),
        "files_indexed": files_indexed,
        "sections_indexed": sections_indexed,
    }
    (index_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def load_vector_index(index_dir: Optional[Path] = None) -> tuple[int, int]:
    global vectorstore, files_indexed, sections_indexed

    if index_dir is None:
        index_dir = INDEX_DIR

    index_file = index_dir / "index.faiss"
    store_file = index_dir / "index.pkl"
    metadata_file = index_dir / "metadata.json"
    if (
        not index_file.exists()
        or not store_file.exists()
        or not metadata_file.exists()
    ):
        vectorstore = None
        files_indexed = 0
        sections_indexed = 0
        return 0, 0

    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    if metadata.get("embedding_model") != EMBEDDING_MODEL:
        raise RuntimeError(
            f"Persisted index uses {metadata.get('embedding_model')}, expected {EMBEDDING_MODEL}"
        )

    current_dimension = embedding_dimension()
    persisted_dimension = metadata.get("embedding_dimension")
    if persisted_dimension != current_dimension:
        raise RuntimeError(
            f"Persisted index dimension is {persisted_dimension}, expected {current_dimension}"
        )

    vectorstore = FAISS.load_local(
        str(index_dir),
        get_embeddings(),
        allow_dangerous_deserialization=True,
    )
    files_indexed = int(metadata.get("files_indexed", 0))
    sections_indexed = int(metadata.get("sections_indexed", 0))
    return files_indexed, sections_indexed


def search(query: str, k: int = 3) -> list[tuple[Document, float]]:
    if vectorstore is None:
        return []

    total_vectors = getattr(vectorstore.index, "ntotal", 0)
    safe_k = min(k, total_vectors)
    if safe_k <= 0:
        return []

    return vectorstore.similarity_search_with_score(query, k=safe_k)
