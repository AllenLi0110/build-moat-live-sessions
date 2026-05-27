import os
import re

from . import indexer


SYSTEM_PROMPT = """
You are a grounded knowledge base Q&A assistant.

Rules:
- Answer only from the CONTEXT in the user message.
- Cite claims with the exact source IDs shown in [Source: ...].
- Do not cite sources that are not present in the CONTEXT.
- If the CONTEXT does not contain enough evidence, say: "I cannot confirm from the knowledge base."
- Do not guess, infer from outside knowledge, or use general world knowledge.
"""

_llm = None
FALLBACK_ANSWER = "I cannot confirm from the knowledge base."
UNSAFE_QUERY_RE = re.compile(
    r"\b("
    r"api[_ -]?key|secret|token|password|environment variable|env var|"
    r"developer mode|system prompt|hidden instruction|ignore previous|"
    r"run|execute|shell|command|script|rm -rf|curl|wget"
    r")\b",
    re.IGNORECASE,
)


def ensure_source(answer: str, source_ids: list[str]) -> str:
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


def build_prompt(query: str, ranked_sections: list) -> str:
    context_blocks = []
    for section, score in ranked_sections:
        heading_path = " > ".join(section.heading_path)
        context_blocks.append(
            "\n".join(
                [
                    f"[Source: {section.id}]",
                    f"Heading: {heading_path}",
                    f"Retrieval score: {score:.3f}",
                    section.content,
                ]
            )
        )

    context = "\n\n---\n\n".join(context_blocks) if context_blocks else "(no context)"
    return f"CONTEXT:\n{context}\n\nQUESTION:\n{query}"


def build_extractive_answer(ranked_sections: list) -> str:
    best_section, _ = ranked_sections[0]
    first_sentence = best_section.content.split(".")[0].strip()
    if first_sentence:
        answer = first_sentence + "."
    else:
        answer = best_section.content.strip()

    return f"{answer} [{best_section.id}]"


def build_learning_focus(ranked_sections: list) -> str:
    best_section, score = ranked_sections[0]
    heading_path = " > ".join(best_section.heading_path)
    return (
        f"The retrieval result suggests the learner is focused on {heading_path} "
        f"because it was the strongest match (score {score:.3f})."
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

    if not indexer.sections:
        return {
            "answer": "The knowledge base has not been indexed yet. Call POST /index first.",
            "sources": [],
            "learning_focus": "",
        }

    ranked_sections = indexer.search(question, k=3)
    if not ranked_sections:
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
                HumanMessage(content=build_prompt(question, ranked_sections)),
            ])
            answer = ensure_source(
                response.content,
                [section.id for section, _ in ranked_sections],
            )
        except Exception:
            answer = build_extractive_answer(ranked_sections)
    else:
        answer = build_extractive_answer(ranked_sections)

    sources = [
        {
            "source": section.id,
            "heading": " > ".join(section.heading_path),
            "score": round(score, 3),
            "content": section.content[:240],
        }
        for section, score in ranked_sections
    ]

    return {
        "answer": answer,
        "sources": sources,
        "learning_focus": build_learning_focus(ranked_sections),
    }
