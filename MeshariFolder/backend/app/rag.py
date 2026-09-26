"""
Retrieval-augmented generation over a company's uploaded knowledge base
(docs/STAGE3_COMPANY_RAG.md). No vector-database dependency: each chunk's
embedding is stored as a plain JSON list[float]
(KnowledgeChunk.embedding_json) and ranked by in-Python cosine similarity
at query time, rather than pgvector or an external vector DB service.
Good enough for a company's knowledge base at this stage's realistic
scale (a handful of job titles, a handful of documents each) — a real
vector index is a contained swap of retrieve()'s internals later, not a
rewrite. See the doc's "Not done" section for exactly what that swap
would involve.
"""
import math

from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    PermissionDeniedError,
    RateLimitError,
)
from sqlalchemy.orm import Session

from app.agents.llm_client import ALL_PROVIDERS_FAILED, openai_client_for_embeddings
from app.models import KnowledgeChunk, KnowledgeMaterial

EMBEDDING_MODEL = "text-embedding-3-small"
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 150
DEFAULT_TOP_K = 5
# One embeddings call per batch of this many chunks — keeps any single
# request comfortably under the API's per-call size limit for a large
# upload, without adding real complexity.
_EMBED_BATCH_SIZE = 96

_EMBEDDING_ERRORS = (
    AuthenticationError,
    PermissionDeniedError,
    RateLimitError,
    APIConnectionError,
    APIStatusError,
)


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Splits on a paragraph or sentence boundary when one falls in the
    back half of the window, otherwise a hard cut at chunk_size. Overlap
    keeps an idea that straddles a boundary from being fully severed in
    both halves."""
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        if end < n:
            boundary = text.rfind("\n\n", start, end)
            if boundary == -1 or boundary <= start + chunk_size // 2:
                boundary = text.rfind(". ", start, end)
            if boundary != -1 and boundary > start + chunk_size // 2:
                end = boundary + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks


def _embed(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    client = openai_client_for_embeddings()
    out: list[list[float]] = []
    try:
        for i in range(0, len(texts), _EMBED_BATCH_SIZE):
            batch = texts[i : i + _EMBED_BATCH_SIZE]
            resp = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
            out.extend(item.embedding for item in resp.data)
    except _EMBEDDING_ERRORS as exc:
        # Reuses the same "clean 503, not a raw 500" path call_agentic/
        # call_with_tool use for a failed provider (main.py's generic
        # RuntimeError handler checks for this exact prefix) — there's no
        # failover chain here (embeddings are OpenAI-only, see
        # llm_client.openai_client_for_embeddings), just the one message.
        raise RuntimeError(f"{ALL_PROVIDERS_FAILED}: embeddings model unavailable ({exc})") from exc
    return out


def embed_query(text: str) -> list[float]:
    return _embed([text])[0]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def ingest_material(
    db: Session,
    *,
    organization_id: str,
    job_title_id: str,
    uploaded_by_user_id: str,
    filename: str | None,
    extracted_text: str,
) -> KnowledgeMaterial:
    """Chunks and embeds one uploaded/pasted source. Stores both the raw
    material (so the company can see what they've uploaded,
    KnowledgeMaterial) and its chunks (what retrieve() actually searches,
    KnowledgeChunk) — a chunk always traces back to the material and job
    title it came from."""
    material = KnowledgeMaterial(
        organization_id=organization_id,
        job_title_id=job_title_id,
        uploaded_by_user_id=uploaded_by_user_id,
        filename=filename,
        extracted_text=extracted_text,
        chunk_count=0,
    )
    db.add(material)
    db.flush()  # material.id, needed before a chunk can reference it

    pieces = chunk_text(extracted_text)
    if pieces:
        vectors = _embed(pieces)
        for i, (piece, vector) in enumerate(zip(pieces, vectors)):
            db.add(
                KnowledgeChunk(
                    organization_id=organization_id,
                    job_title_id=job_title_id,
                    material_id=material.id,
                    chunk_index=i,
                    content=piece,
                    embedding_json=vector,
                )
            )
    material.chunk_count = len(pieces)
    db.commit()
    db.refresh(material)
    return material


def retrieve(
    db: Session, job_title_id: str, query: str, k: int = DEFAULT_TOP_K
) -> list[tuple[float, KnowledgeChunk]]:
    """Every chunk under this job title, ranked by cosine similarity to
    the query, top k — returned as (score, chunk) pairs so a caller can
    show or threshold on the score rather than just trusting the order.
    O(n) in Python over however many chunks this job title has — fine at
    a single company's realistic scale; see the module docstring for the
    upgrade path if that stops being true."""
    chunks = db.query(KnowledgeChunk).filter(KnowledgeChunk.job_title_id == job_title_id).all()
    if not chunks:
        return []
    query_vector = embed_query(query)
    scored = [(_cosine_similarity(query_vector, c.embedding_json), c) for c in chunks]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[:k]
