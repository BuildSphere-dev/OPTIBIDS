# backend/app/tasks.py

"""
Celery tasks for async proposal evaluation.

Flow per task:
  1. Load TenderChunks from DB (with metadata → LangChain Documents)
  2. Build FAISS index from chunk embeddings
  3. Embed proposal text → vector search → retrieve top-k relevant chunks
  4. Call scorer.score_proposal(relevant_docs, proposal_text)
  5. Persist scores on Application row
  6. If new score > tender.best_score → update tender.best_proposal_id  (O(1) winner)
"""

import json
from typing import List, Sequence

from langchain_core.documents import Document
from sqlmodel import select

from .celery_app import celery
from .db import get_session
from .models import Application, Tender, TenderChunk
from .scorer import score_proposal
from . import ai_agent, matcher



def _chunks_to_documents(chunks: Sequence[TenderChunk]) -> List[Document]:
    """
    Convert TenderChunk ORM rows into LangChain Document objects,
    re-attaching the metadata that was stored at index time.
    """
    docs = []
    for chunk in chunks:
        # metadata was stored in the TenderChunk row itself
        # so we reconstruct it here for the retriever
        doc = Document(
            page_content=chunk.chunk_text,
            metadata={
                "tender_id": chunk.tender_id,
                "tender_title": chunk.tender_title,   # stored at index time
                "chunk_index": chunk.chunk_index,
                "total_chunks": chunk.total_chunks,   # stored at index time
                "source": "tender",
                "chunk_db_id": chunk.id,
            },
        )
        docs.append(doc)
    return docs


# ---------------------------------------------------------------------------
# Helper: vector retrieval
# ---------------------------------------------------------------------------

def _retrieve_relevant_chunks(
    all_chunks: List[TenderChunk],
    all_docs: List[Document],
    proposal_text: str,
    top_k: int = 5,
) -> List[Document]:
    """
    Build a FAISS index from all tender chunks for this tender,
    then retrieve the top_k most relevant ones for the proposal.

    Falls back to the first top_k chunks if FAISS fails.
    """
    if not all_chunks:
        return []

    # Only chunks that have embeddings stored
    valid_pairs = [
        (chunk, doc)
        for chunk, doc in zip(all_chunks, all_docs)
        if chunk.embedding_json is not None
    ]

    if not valid_pairs:
        return all_docs[:top_k]

    try:
        vectors = []
        valid_docs = []
        for chunk, doc in valid_pairs:
            assert chunk.embedding_json is not None
            vectors.append(json.loads(chunk.embedding_json))
            valid_docs.append(doc)

        matcher.build_index(vectors)

        query_vec = ai_agent.embed_text(proposal_text[:1000])
        ids, _ = matcher.search_index(query_vec, top_k=top_k)

        return [valid_docs[i] for i in ids if i < len(valid_docs)]

    except Exception as e:
        print(f"⚠️  tasks: FAISS retrieval failed, using first {top_k} chunks: {e}")
        return all_docs[:top_k]


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------

@celery.task(bind=True, queue="pdf_queue", max_retries=2, default_retry_delay=30)
def evaluate_proposal(self, application_id: int) -> None:
    """
    Async task: score a proposal against its tender.

    Queued by submit_application immediately after saving the Application row.
    The API returns 200 to the bidder before this task runs.

    Args:
        application_id: PK of the Application row to evaluate.
    """
    print(f"▶  evaluate_proposal: application_id={application_id}")

    try:
        with get_session() as session:
            # ── 1. Load application ──────────────────────────────────────────
            app = session.get(Application, application_id)
            if not app:
                print(f"   Application {application_id} not found — skipping")
                return

            # ── 2. Load all tender chunks for this tender ────────────────────
            chunks: List[TenderChunk] = list(session.exec(
                select(TenderChunk)
                .where(TenderChunk.tender_id == app.tender_id)
                .order_by(TenderChunk.chunk_index)  # type: ignore[arg-type]
            ).all())

            if not chunks:
                print(
                    f"   No TenderChunks for tender_id={app.tender_id} — retrying in 15s"
                )
                raise self.retry(
                    exc=Exception("Tender not indexed yet"),
                    countdown=15,
                )

            # ── 3. Convert to LangChain Documents (metadata re-attached) ────
            all_docs = _chunks_to_documents(chunks)

            # ── 4. RAG: retrieve top-5 relevant chunks ───────────────────────
            relevant_docs = _retrieve_relevant_chunks(
                all_chunks=chunks,
                all_docs=all_docs,
                proposal_text=app.applicant_text,
                top_k=5,
            )

            print(
                f"   Retrieved {len(relevant_docs)} relevant chunks "
                f"from {len(chunks)} total for tender_id={app.tender_id}"
            )

            # ── 5. LLM scoring ───────────────────────────────────────────────
            scores = score_proposal(
                relevant_chunks=relevant_docs,
                proposal_text=app.applicant_text,
            )

            # ── 6. Persist scores on Application ────────────────────────────
            app.overall_score = scores["overall_score"]
            app.technical_score = scores["technical_score"]
            app.pricing_score = scores["pricing_score"]
            app.compliance_score = scores["compliance_score"]
            app.score_summary = scores["summary"]
            app.status = "evaluated"
            session.add(app)
            session.flush()  # write scores before checking winner

            # ── 7. Update winner — O(1) ──────────────────────────────────────
            tender = session.get(Tender, app.tender_id)
            if tender and app.overall_score > (tender.best_score or 0.0):
                prev_best = tender.best_proposal_id
                tender.best_proposal_id = app.id
                tender.best_score = app.overall_score
                session.add(tender)
                print(
                    f"   🏆 New winner: application_id={app.id} "
                    f"score={app.overall_score} "
                    f"(prev best_proposal_id={prev_best})"
                )

            session.commit()
            print(f"✅  evaluate_proposal done: application_id={application_id} "
                  f"overall_score={app.overall_score}")

    except Exception as exc:
        print(f"❌  evaluate_proposal failed for application_id={application_id}: {exc}")
        # Celery retry with exponential backoff
        raise self.retry(exc=exc)
