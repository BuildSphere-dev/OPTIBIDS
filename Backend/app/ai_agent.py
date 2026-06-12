# backend/app/ai_agent.py

"""
AI agent helpers.

Changes from v1:
  - build_user_summary now takes (tender_id, session) and reads scores
    from the database. No Ollama call. No applications list passed in.
  - All other functions (extract_requirements_from_text,
    generate_proposal_text, embed_text) are unchanged.
"""

import os
import json
import hashlib
import requests
from typing import List, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlmodel import Session

OLLAMA_BASE = os.environ.get("OLLAMA_BASE", "http://localhost:11434")
OLLAMA_GENERATE = f"{OLLAMA_BASE}/api/generate"
MODEL = os.environ.get("OLLAMA_MODEL", "phi3:mini")


# ---------------------------------------------------------------------------
# Unchanged functions
# ---------------------------------------------------------------------------

def extract_requirements_from_text(text: str) -> Dict:
    prompt = f"""
You are an information extraction system.

Extract clear, atomic requirements from the following tender.

Return ONLY valid JSON in this exact format (no explanation, no markdown):

{{
  "requirements": [
    {{"text": "requirement description", "quantity": 1}}
  ],
  "confidence": 0.9
}}

Tender text:
{text}
"""
    r = None
    try:
        r = requests.post(
            OLLAMA_GENERATE,
            json={"model": MODEL, "prompt": prompt, "stream": False},
            timeout=120,
        )
        r.raise_for_status()

        raw = r.json().get("response", "").strip()
        if not raw:
            raise ValueError("Empty response from Ollama")

        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == -1:
            raise ValueError("No JSON found in model output")

        data = json.loads(raw[start:end])
        if "requirements" not in data:
            raise ValueError("Missing 'requirements' key")
        return data

    except Exception as e:
        print("❌ Requirement extraction failed:", e)
        if r is not None:
            print("Raw Ollama output:", r.text)
        return {"requirements": [], "confidence": 0.0}


def generate_proposal_text(
    requirements: Dict,
    applicant_info: Dict,
    pricing: Dict,
) -> str:
    """Generate proposal text (optional helper). Unchanged."""
    prompt = f"""
Create a professional proposal based on:

Requirements:
{requirements}

Applicant:
{applicant_info}

Pricing:
{pricing}
"""
    try:
        r = requests.post(
            OLLAMA_GENERATE,
            json={"model": MODEL, "prompt": prompt, "stream": False},
            timeout=120,
        )
        r.raise_for_status()
        return r.json().get("response", "Draft proposal unavailable")
    except Exception as e:
        print("❌ Proposal generation failed:", e)
        return "Draft proposal unavailable"


def embed_text(text: str) -> List[float]:
    """
    Deterministic lightweight embedding (MD5-based mock).
    Safe for FAISS testing. Replace with a real embedding model in production.
    """
    h = hashlib.md5(text.encode()).digest()
    return [b / 255 for b in h]


# ---------------------------------------------------------------------------
# Updated: build_user_summary — pure DB read, no LLM
# ---------------------------------------------------------------------------

def build_user_summary(tender_id: int, session: "Session") -> dict:
    """
    Build a ranked summary of all evaluated proposals for a tender.

    Reads scores directly from the Application table.
    Does NOT call Ollama. Does NOT accept an applications list.

    Args:
        tender_id : PK of the tender to summarise.
        session   : Active SQLModel session (caller owns it).

    Returns:
        {
          "best_application": { ... } | None,
          "comparison": [ { ... }, ... ]   # all evaluated apps, best-first
        }
    """
    from sqlmodel import select
    from .models import Application, User, Tender

    # Fetch all evaluated applications for this tender, best score first
    apps = session.exec(
        select(Application)
        .where(Application.tender_id == tender_id)
        .where(Application.status == "evaluated")
        .order_by(Application.overall_score.desc()) # type: ignore
    ).all()

    fallback = False
    if not apps:
        # If no applications have been evaluated yet, return submitted proposals
        apps = session.exec(
            select(Application)
            .where(Application.tender_id == tender_id)
            .order_by(Application.created_at.desc()) # type: ignore
        ).all()
        fallback = True

    if not apps:
        return {"best_application": None, "comparison": []}

    def _user_email(user_id: int) -> str:
        user = session.get(User, user_id)
        return user.email if user else "unknown"

    def _app_to_dict(app: Application) -> dict:
        return {
            "application_id": app.id,
            "email": _user_email(app.user_id),
            "overall_score": app.overall_score,
            "technical_score": app.technical_score,
            "pricing_score": app.pricing_score,
            "compliance_score": app.compliance_score,
            "summary": app.score_summary or "",
            "status": app.status,
            "created_at": app.created_at.isoformat() if app.created_at else None,
        }

    best = apps[0]

    # Also read tender.best_proposal_id to confirm it matches
    tender = session.get(Tender, tender_id)
    confirmed_winner_id = tender.best_proposal_id if tender else None

    return {
        "best_application": {
            **_app_to_dict(best),
            "is_confirmed_winner": confirmed_winner_id == best.id,
            "note": "Evaluation pending" if fallback and best.status != "evaluated" else None,
        },
        "comparison": [_app_to_dict(a) for a in apps],
        "pending_evaluation": fallback,
    }
