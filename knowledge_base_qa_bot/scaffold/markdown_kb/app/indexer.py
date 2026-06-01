import math
import re
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Optional


DOCS_DIR = Path(__file__).resolve().parents[3] / "docs"
INDEX_PATH = Path(__file__).resolve().parents[3] / ".kb" / "index.json"
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
TOKEN_RE = re.compile(r"[a-z0-9]+")
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "can",
    "do",
    "does",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "my",
    "now",
    "of",
    "on",
    "or",
    "the",
    "to",
    "you",
    "your",
    "what",
    "when",
    "which",
    "with",
}


@dataclass
class Section:
    id: str
    file: str
    heading: str
    heading_path: list[str]
    content: str
    tokens: list[str]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "file": self.file,
            "heading": self.heading,
            "heading_path": self.heading_path,
            "content": self.content,
            "tokens": self.tokens,
        }


sections: list[Section] = []
doc_freq: Counter[str] = Counter()
avg_doc_len = 0.0
files_indexed = 0


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOP_WORDS]


def parse_markdown(path: Path) -> list[Section]:
    parsed_sections: list[Section] = []
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

        heading_text = " ".join(current_path)
        section_tokens = tokenize(f"{heading_text}\n{content}")
        parsed_sections.append(
            Section(
                id=f"{path.name}#{slugify(current_heading)}",
                file=path.name,
                heading=current_heading,
                heading_path=current_path.copy(),
                content=content,
                tokens=section_tokens,
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
    return parsed_sections


def write_index_json(index_path: Optional[Path] = None) -> None:
    if index_path is None:
        index_path = INDEX_PATH

    index_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "sections": [section.to_dict() for section in sections],
        "stats": {
            "files_indexed": files_indexed,
            "sections_indexed": len(sections),
            "avg_doc_len": avg_doc_len,
            "doc_freq": dict(sorted(doc_freq.items())),
        },
    }
    index_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def rebuild_stats() -> None:
    global doc_freq, avg_doc_len, files_indexed

    doc_freq = Counter()
    files_indexed = len({section.file for section in sections})
    total_tokens = 0

    for section in sections:
        total_tokens += len(section.tokens)
        doc_freq.update(set(section.tokens))

    avg_doc_len = total_tokens / len(sections) if sections else 0.0


def load_index_json(index_path: Optional[Path] = None) -> tuple[int, int]:
    global sections

    if index_path is None:
        index_path = INDEX_PATH

    if not index_path.exists():
        sections = []
        rebuild_stats()
        return 0, 0

    payload = json.loads(index_path.read_text(encoding="utf-8"))
    sections = [
        Section(
            id=item["id"],
            file=item["file"],
            heading=item["heading"],
            heading_path=list(item["heading_path"]),
            content=item["content"],
            tokens=list(item["tokens"]),
        )
        for item in payload.get("sections", [])
    ]
    rebuild_stats()
    return files_indexed, len(sections)


def list_documents() -> list[dict]:
    documents: dict[str, list[dict]] = {}
    for section in sections:
        documents.setdefault(section.file, []).append(
            {
                "source": section.id,
                "heading": " > ".join(section.heading_path),
            }
        )

    return [
        {
            "file": file,
            "sections": file_sections,
        }
        for file, file_sections in sorted(documents.items())
    ]


def build_index(docs_dir: Path = DOCS_DIR) -> tuple[int, int]:
    global sections

    sections = []
    for path in sorted(docs_dir.glob("*.md")):
        sections.extend(parse_markdown(path))

    rebuild_stats()
    write_index_json()
    return files_indexed, len(sections)


def bm25_score(query_tokens: list[str], section: Section, k1: float = 1.5, b: float = 0.75) -> float:
    if not query_tokens or not sections or avg_doc_len <= 0:
        return 0.0

    token_counts = Counter(section.tokens)
    section_len = len(section.tokens) or 1
    total_sections = len(sections)
    score = 0.0

    for token in query_tokens:
        term_frequency = token_counts[token]
        if term_frequency == 0:
            continue

        containing_docs = doc_freq[token]
        idf = math.log(1 + (total_sections - containing_docs + 0.5) / (containing_docs + 0.5))
        denominator = term_frequency + k1 * (1 - b + b * section_len / avg_doc_len)
        score += idf * (term_frequency * (k1 + 1)) / denominator

    heading_tokens = set(tokenize(" ".join(section.heading_path)))
    heading_matches = sum(1 for token in query_tokens if token in heading_tokens)
    return score + (heading_matches * 0.35)


def search(query: str, k: int = 3) -> list[tuple[Section, float]]:
    query_tokens = tokenize(query)
    ranked = [
        (section, bm25_score(query_tokens, section))
        for section in sections
    ]
    ranked.sort(key=lambda item: item[1], reverse=True)
    return [(section, score) for section, score in ranked[:k] if score > 0]
