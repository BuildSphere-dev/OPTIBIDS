# backend/app/pipeline.py

"""
Tender indexing pipeline.

Triggered when an admin publishes a tender.
Runs in a background thread (never blocks the API response).

What it does:
  1. Extract text from the tender (raw_text or description)
  2. Chunk it using LangChain RecursiveCharacterTextSplitter
  3. Embed each chunk (ai_agent.embed_text)
  4. Store TenderChunk rows with metadata + embedding_json
  5. Set tender.status = "published"

Proposal scoring is handled separately by tasks.evaluate_proposal (Celery).

The old run_pipeline function is preserved below for backward compatibility
in case any internal code still references it.
"""

import json
from sqlmodel import select

from .db import get_session
from .models import Tender, TenderChunk
from . import ai_agent
from .chunker import chunk_tender


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def index_tender(tender_id: int) -> None:
    """
    Chunk and embed a tender's text, storing each chunk as a TenderChunk row.

    Called by the admin publish endpoint via FastAPI's BackgroundTasks or
    run_in_threadpool so the HTTP response returns immediately.

    Args:
        tender_id: PK of the Tender to index.
    """
    print(f"▶  index_tender: tender_id={tender_id}")

    # ── Load tender ──────────────────────────────────────────────────────────
    with get_session() as session:
        tender = session.get(Tender, tender_id)
        if tender is None:
            print(f"   Tender {tender_id} not found — aborting")
            return

        tender.status = "indexing"
        session.commit()

        tender_title = tender.title
        text = tender.raw_text or tender.description

    # ── Chunk with LangChain (metadata attached per Document) ────────────────
    documents = chunk_tender(
        text=text,
        tender_id=tender_id,
        tender_title=tender_title,
        chunk_size=500,
        chunk_overlap=100,
    )

    print(f"   Produced {len(documents)} chunks for tender_id={tender_id}")

    # ── Embed + persist ──────────────────────────────────────────────────────
    with get_session() as session:
        # Clear any previously indexed chunks for this tender
        # (handles re-indexing after an edit)
        old_chunks = session.exec(
            select(TenderChunk).where(TenderChunk.tender_id == tender_id)
        ).all()
        for old in old_chunks:
            session.delete(old)
        session.flush()

        for doc in documents:
            meta = doc.metadata
            embedding = ai_agent.embed_text(doc.page_content)

            session.add(
                TenderChunk(
                    tender_id=tender_id,
                    chunk_index=meta["chunk_index"],
                    total_chunks=meta["total_chunks"],
                    chunk_text=doc.page_content,
                    tender_title=meta.get("tender_title", ""),
                    embedding_json=json.dumps(embedding),
                )
            )

        tender = session.get(Tender, tender_id)
        if tender:
            tender.status = "published"
        session.commit()

    print(f"✅  index_tender done: {len(documents)} chunks stored, "
          f"tender_id={tender_id} status=published")


# ---------------------------------------------------------------------------
# Legacy — kept so any existing imports of run_pipeline don't break
# ---------------------------------------------------------------------------

def run_pipeline(tender_id: int) -> None:
    """
    Deprecated: was the old synchronous proposal pipeline.
    Now simply delegates to index_tender.
    Kept for backward compatibility only.
    """
    print("⚠️  run_pipeline is deprecated — calling index_tender instead")
    index_tender(tender_id)
