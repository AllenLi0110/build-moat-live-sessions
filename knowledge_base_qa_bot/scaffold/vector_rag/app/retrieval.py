import os
import re

from . import indexer


SYSTEM_PROMPT = """
You are a grounded vector RAG knowledge base Q&A assistant.

Rules:
- Answer only from the CONTEXT in the user message.
- Cite claims with the exact source IDs shown in [Source: ...].
- Do not cite sources that are not present in the CONTEXT.
- If the CONTEXT does not contain enough evidence, say: "I cannot confirm from the knowledge base."
- Do not guess, infer from outside knowledge, or use general world knowledge.
"""

_llm = None
FALLBACK_ANSWER = "I cannot confirm from the knowledge base."
MAX_VECTOR_DISTANCE = float(os.getenv("VECTOR_RAG_MAX_DISTANCE", "1.25"))
UNSAFE_QUERY_RE = re.compile(
    r"\b("
    r"api[_ -]?key|secret|token|password|environment variable|env var|"
    r"developer mode|system prompt|hidden instruction|ignore previous|"
    r"run|execute|shell|command|script|rm -rf|curl|wget"
    r")\b",
    re.IGNORECASE,
)


def ensure_source(answer: str, source_ids: list[str]) -> str:
    if answer.strip().startswith(FALLBACK_ANSWER):
        return FALLBACK_ANSWER

    if any(source_id in answer for source_id in source_ids):
        return answer
    return f"{answer.rstrip()} [{source_ids[0]}]"


def get_llm():
    global _llm
    if _llm is None:
        from langchain_groq import ChatGroq

        _llm = ChatGroq(
            model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
            temperature=0,
            timeout=20,
            max_retries=1,
        )
    return _llm


def build_prompt(query: str, ranked_chunks: list) -> str:
    context_blocks = []
    for doc, score in ranked_chunks:
        context_blocks.append(
            "\n".join(
                [
                    f"[Source: {doc.metadata.get('source', 'unknown')}]",
                    f"Heading: {doc.metadata.get('heading', 'unknown')}",
                    f"Vector distance: {float(score):.3f}",
                    doc.page_content,
                ]
            )
        )

    context = "\n\n---\n\n".join(context_blocks) if context_blocks else "(no context)"
    return f"CONTEXT:\n{context}\n\nQUESTION:\n{query}"


def build_extractive_answer(ranked_chunks: list) -> str:
    best_doc, _ = ranked_chunks[0]
    source = best_doc.metadata.get("source", "unknown")
    content = best_doc.page_content.split("\n\n", 1)[-1].strip()
    first_sentence = content.split(".")[0].strip()
    answer = f"{first_sentence}." if first_sentence else content
    return f"{answer} [{source}]"


def build_learning_focus(ranked_chunks: list) -> str:
    best_doc, score = ranked_chunks[0]
    heading = best_doc.metadata.get("heading", "unknown")
    return (
        f"The vector retrieval result suggests the learner is focused on {heading} "
        f"because it was the nearest chunk (distance {float(score):.3f})."
    )


def is_unsafe_query(question: str) -> bool:
    return bool(UNSAFE_QUERY_RE.search(question))


def query(question: str) -> dict:
    if is_unsafe_query(question):
        return {
            "answer": FALLBACK_ANSWER,
            "sources": [],
            "learning_focus": "",
        }

    if indexer.vectorstore is None:
        return {
            "answer": "The knowledge base has not been indexed yet. Call POST /index first.",
            "sources": [],
            "learning_focus": "",
        }

    try:
        ranked_chunks = indexer.search(question, k=3)
    except Exception:
        return {
            "answer": "Vector RAG could not query embeddings. Check the local embedding setup or index state.",
            "sources": [],
            "learning_focus": "",
        }

    if not ranked_chunks or float(ranked_chunks[0][1]) > MAX_VECTOR_DISTANCE:
        return {
            "answer": FALLBACK_ANSWER,
            "sources": [],
            "learning_focus": "",
        }

    if os.getenv("GROQ_API_KEY"):
        from langchain.schema import HumanMessage, SystemMessage

        try:
            response = get_llm().invoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=build_prompt(question, ranked_chunks)),
            ])
            answer = ensure_source(
                response.content,
                [doc.metadata.get("source", "unknown") for doc, _ in ranked_chunks],
            )
        except Exception:
            answer = build_extractive_answer(ranked_chunks)
    else:
        answer = build_extractive_answer(ranked_chunks)

    sources = [
        {
            "source": doc.metadata.get("source", "unknown"),
            "heading": doc.metadata.get("heading", "unknown"),
            "score": round(float(score), 3),
            "content": doc.page_content[:240],
        }
        for doc, score in ranked_chunks
    ]

    return {
        "answer": answer,
        "sources": sources,
        "learning_focus": build_learning_focus(ranked_chunks),
    }
