from __future__ import annotations

import hashlib
import math
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models import ConceptPage, EmbeddingChunk, IndexJob
from app.services.context_compiler import tiptap_to_text
from app.services.model_gateway import ModelGateway, ModelGatewayError

FACT_ROLES = {"PROJECT_CANON", "DRAFT_SETTING", "CANON_EVIDENCE", "SECONDARY_INTERPRETATION"}


def _chunks(value: str, *, size: int = 1200, overlap: int = 120) -> list[str]:
    normalized = "\n".join(line.strip() for line in value.splitlines() if line.strip())
    if not normalized:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + size)
        chunks.append(normalized[start:end])
        if end == len(normalized):
            break
        start = max(start + 1, end - overlap)
    return chunks


def page_chunks(page: ConceptPage) -> list[str]:
    body = tiptap_to_text(page.body_json)
    value = "\n".join(
        part
        for part in [page.title, page.summary, *page.locked_facts, body]
        if isinstance(part, str) and part.strip()
    )
    return _chunks(value)


async def run_index_job(db: Session, job: IndexJob, gateway: ModelGateway | None = None) -> IndexJob:
    gateway = gateway or ModelGateway()
    job.status = "RUNNING"
    job.attempt_count += 1
    job.error_json = {}
    db.add(job)
    db.commit()
    try:
        stmt = select(ConceptPage).where(ConceptPage.project_id == job.project_id)
        if job.concept_page_id:
            stmt = stmt.where(ConceptPage.id == job.concept_page_id)
        pages = list(db.scalars(stmt).all())
        indexed = 0
        removed = 0
        for page in pages:
            result = db.execute(
                delete(EmbeddingChunk).where(
                    EmbeddingChunk.project_id == job.project_id,
                    EmbeddingChunk.source_id == page.id,
                )
            )
            removed += int(result.rowcount or 0)
            if page.status == "rejected" or page.usage_role == "REJECTED":
                continue
            chunks = page_chunks(page)
            if not chunks or not settings.embedding_enabled:
                continue
            vectors: list[list[float]] = []
            for start in range(0, len(chunks), settings.embedding_batch_size):
                batch_vectors, _ = await gateway.embed(chunks[start : start + settings.embedding_batch_size])
                vectors.extend(batch_vectors)
            scope = "DISCOURSE" if page.usage_role == "DISCOURSE_REFERENCE" else "FACT"
            for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
                db.add(
                    EmbeddingChunk(
                        project_id=page.project_id,
                        concept_page_id=page.id,
                        source_id=page.id,
                        universe_namespace=page.namespace,
                        source_role=page.usage_role,
                        index_scope=scope,
                        chunk_index=index,
                        chunk_text=chunk,
                        search_text=chunk,
                        chunk_hash=hashlib.sha256(chunk.encode("utf-8")).hexdigest(),
                        embedding=vector,
                        embedding_model=settings.embedding_model,
                        embedding_dimension=settings.embedding_dimension,
                        embedding_version=settings.embedding_version,
                    )
                )
                indexed += 1
        job.status = "COMPLETED"
        job.stats_json = {"pages": len(pages), "chunks": indexed, "removed": removed}
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    except Exception as exc:
        db.rollback()
        job = db.get(IndexJob, job.id) or job
        job.status = "FAILED"
        code = exc.code if isinstance(exc, ModelGatewayError) else "INDEXING_FAILED"
        job.error_json = {"code": code, "message": str(exc)}
        db.add(job)
        db.commit()
        db.refresh(job)
        return job


def _rrf(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank)


async def hybrid_search(
    db: Session,
    *,
    project_id: str,
    query: str,
    selected_page_ids: list[str] | None = None,
    namespaces: list[str] | None = None,
    source_roles: list[str] | None = None,
    factual_only: bool = True,
    limit: int = 20,
    gateway: ModelGateway | None = None,
) -> dict[str, Any]:
    selected_page_ids = selected_page_ids or []
    namespaces = namespaces or []
    roles = source_roles or sorted(FACT_ROLES)
    if factual_only:
        roles = [role for role in roles if role in FACT_ROLES]

    page_stmt = select(ConceptPage).where(
        ConceptPage.project_id == project_id,
        ConceptPage.status != "rejected",
        ConceptPage.usage_role.in_(roles),
    )
    if namespaces:
        page_stmt = page_stmt.where(ConceptPage.namespace.in_(namespaces))
    pages = list(db.scalars(page_stmt).all())
    by_id = {page.id: page for page in pages}

    lowered = query.casefold().strip()
    lexical = sorted(
        (
            (
                page.id,
                sum(
                    text_value.casefold().count(lowered)
                    for text_value in [page.title, page.summary, tiptap_to_text(page.body_json)]
                    if lowered and text_value
                ),
            )
            for page in pages
        ),
        key=lambda item: (-item[1], item[0]),
    )
    lexical = [item for item in lexical if item[1] > 0]

    dense_rows: list[tuple[str, float, str]] = []
    dense_error: dict[str, str] | None = None
    if settings.embedding_enabled and query.strip() and db.bind and db.bind.dialect.name == "postgresql":
        try:
            gateway = gateway or ModelGateway()
            vectors, _ = await gateway.embed([query])
            vector_literal = "[" + ",".join(f"{value:.9g}" for value in vectors[0]) + "]"
            sql = """
                SELECT concept_page_id,
                       1 - (embedding <=> CAST(:query_vector AS vector)) AS score,
                       chunk_text
                FROM lore_vector.embedding_chunks
                WHERE project_id = :project_id
                  AND index_scope = 'FACT'
                  AND source_role = ANY(:roles)
            """
            params: dict[str, Any] = {
                "query_vector": vector_literal,
                "project_id": project_id,
                "roles": roles,
                "limit": max(limit * 3, 30),
            }
            if namespaces:
                sql += " AND universe_namespace = ANY(:namespaces)"
                params["namespaces"] = namespaces
            sql += " ORDER BY embedding <=> CAST(:query_vector AS vector) LIMIT :limit"
            dense_rows = [
                (str(row.concept_page_id), float(row.score), str(row.chunk_text))
                for row in db.execute(text(sql), params)
                if row.concept_page_id
            ]
        except (ModelGatewayError, ValueError) as exc:
            dense_error = {
                "code": getattr(exc, "code", "DENSE_SEARCH_FAILED"),
                "message": str(exc),
            }

    scores: dict[str, float] = {}
    reasons: dict[str, list[str]] = {}
    excerpts: dict[str, str] = {}
    for rank, (page_id, _) in enumerate(lexical, start=1):
        scores[page_id] = scores.get(page_id, 0.0) + _rrf(rank)
        reasons.setdefault(page_id, []).append("전문/키워드")
    seen_dense: set[str] = set()
    for rank, (page_id, _, excerpt) in enumerate(dense_rows, start=1):
        if page_id in seen_dense:
            continue
        seen_dense.add(page_id)
        scores[page_id] = scores.get(page_id, 0.0) + _rrf(rank)
        reasons.setdefault(page_id, []).append("BGE-M3 Dense")
        excerpts[page_id] = excerpt
    for page_id in reversed(selected_page_ids):
        page = db.get(ConceptPage, page_id)
        if page and page.project_id == project_id:
            by_id[page.id] = page
            scores[page.id] = math.inf
            reasons.setdefault(page.id, []).append("사용자 명시 선택")

    ordered = sorted(scores, key=lambda item: (-scores[item], item))[:limit]
    return {
        "query": query,
        "results": [
            {
                "page_id": page_id,
                "title": by_id[page_id].title,
                "namespace": by_id[page_id].namespace,
                "source_role": by_id[page_id].usage_role,
                "score": None if math.isinf(scores[page_id]) else scores[page_id],
                "reasons": reasons.get(page_id, []),
                "excerpt": excerpts.get(page_id, by_id[page_id].summary),
                "explicitly_selected": page_id in selected_page_ids,
            }
            for page_id in ordered
            if page_id in by_id
        ],
        "dense_error": dense_error,
        "embedding_enabled": settings.embedding_enabled,
    }


def index_stats(db: Session, project_id: str) -> dict[str, Any]:
    chunk_count = db.scalar(
        select(func.count(EmbeddingChunk.id)).where(EmbeddingChunk.project_id == project_id)
    )
    page_count = db.scalar(
        select(func.count(func.distinct(EmbeddingChunk.source_id))).where(
            EmbeddingChunk.project_id == project_id
        )
    )
    jobs = db.execute(
        select(IndexJob.status, func.count(IndexJob.id))
        .where(IndexJob.project_id == project_id)
        .group_by(IndexJob.status)
    ).all()
    return {
        "project_id": project_id,
        "chunks": int(chunk_count or 0),
        "indexed_pages": int(page_count or 0),
        "jobs": {status: count for status, count in jobs},
        "model": settings.embedding_model,
        "dimension": settings.embedding_dimension,
        "version": settings.embedding_version,
    }
