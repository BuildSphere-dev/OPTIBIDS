# backend/app/scorer.py

"""
LLM-based proposal scoring.

Called ONLY from Celery tasks — never directly from API route handlers.
Uses relevant tender chunks (retrieved via RAG) instead of the full tender
text, so the prompt stays small and focused.
"""

import json
import os
import requests
from typing import List

from langchain_core.documents import Document


OLLAMA_BASE = os.environ.get("OLLAMA_BASE", "http://localhost:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "phi3:mini")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_context(docs: List[Document]) -> str:
    """
    Format a list of LangChain Documents into a readable context block
    that is injected into the LLM prompt.

    Each chunk includes its metadata so the model knows which part of
    the tender it is looking at.
    """
    parts = []
    for doc in docs:
        meta = doc.metadata
        header = (
            f"[Tender: {meta.get('tender_title', 'N/A')} | "
            f"Chunk {meta.get('chunk_index', '?')} / {meta.get('total_chunks', '?')}]"
        )
        parts.append(f"{header}\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)


def _call_ollama(prompt: str, timeout: int = 180) -> str:
    """Raw Ollama call. Returns the model's text response."""
    r = requests.post(
        f"{OLLAMA_BASE}/api/generate",
        json={"model": MODEL, "prompt": prompt, "stream": False},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json().get("response", "").strip()


def _parse_json(raw: str) -> dict:
    """Extract the first valid JSON object from a model response."""
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON object found in model output:\n{raw}")
    return json.loads(raw[start:end])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_proposal(
    relevant_chunks: List[Document],
    proposal_text: str,
) -> dict:
    """
    Score a proposal against the most relevant tender chunks.

    Args:
        relevant_chunks : List of LangChain Documents retrieved via
                          vector search for this proposal.
        proposal_text   : Full text of the applicant's proposal.

    Returns:
        Dict with keys:
            overall_score    : float  0–100
            technical_score  : float  0–100
            pricing_score    : float  0–100
            compliance_score : float  0–100
            summary          : str    2-3 sentence evaluation
    """
    context = _build_context(relevant_chunks)

    prompt = f"""You are an expert RFP (Request for Proposal) evaluator.

Below are the most relevant sections of the tender document, followed by
the applicant's proposal. Evaluate how well the proposal addresses the
tender requirements.

=== TENDER CONTEXT ===
{context}

=== APPLICANT PROPOSAL ===
{proposal_text}

=== INSTRUCTIONS ===
Evaluate the proposal on four dimensions and return ONLY valid JSON.
No explanation, no markdown, no preamble.

{{
  "overall_score": <integer 0-100>,
  "technical_score": <integer 0-100>,
  "pricing_score": <integer 0-100>,
  "compliance_score": <integer 0-100>,
  "summary": "<2-3 sentence professional evaluation>"
}}

Scoring guide:
- overall_score   : weighted average of the three below
- technical_score : how well the proposal meets technical requirements
- pricing_score   : competitiveness and clarity of pricing
- compliance_score: adherence to stated tender requirements and format
"""

    try:
        raw = _call_ollama(prompt)
        result = _parse_json(raw)

        # Clamp all scores to 0–100
        for key in ("overall_score", "technical_score", "pricing_score", "compliance_score"):
            result[key] = max(0.0, min(100.0, float(result.get(key, 0))))

        result.setdefault("summary", "No summary provided.")
        return result

    except Exception as e:
        print(f"❌ scorer: scoring failed: {e}")
        return {
            "overall_score": 0.0,
            "technical_score": 0.0,
            "pricing_score": 0.0,
            "compliance_score": 0.0,
            "summary": f"Scoring failed: {e}",
        }
