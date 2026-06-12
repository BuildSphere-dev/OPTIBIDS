# backend/app/routes_applicant.py

from fastapi import APIRouter, HTTPException, Depends, Body
from sqlmodel import select
import json
from typing import Optional

from .db import get_session
from .auth_helpers import get_current_user
from .models import Application, Tender, User
from .celery_app import celery

router = APIRouter()


# -------------------------------------------------
# AUTH helpers
# -------------------------------------------------
def require_applicant(user: User = Depends(get_current_user)):
    if user.role not in ("applicant", "admin"):
        raise HTTPException(403, "Applicants only")
    if user.id is None:
        raise HTTPException(status_code=500, detail="Authenticated user has no ID")
    return user


# -------------------------------------------------
# SUBMIT APPLICATION  (no route change — queues Celery task)
# -------------------------------------------------
@router.post("/submit_application")
def submit_application(data: dict, user: User = Depends(require_applicant)):
    if user.id is None:
        raise HTTPException(status_code=500, detail="Authenticated user has no ID")
    user_id = user.id

    tender_id = data.get("tender_id")
    if not tender_id:
        raise HTTPException(status_code=422, detail="tender_id is required")

    with get_session() as session:
        app = Application(
            tender_id=int(tender_id),
            user_id=user_id,
            applicant_text=data.get("text", ""),
            pdf_path=data.get("pdf_path"),
            status="submitted",
        )
        session.add(app)
        session.commit()
        session.refresh(app)
        app_id = app.id

    # Queue async scoring — bidder does NOT wait for LLM
    celery.send_task(
        "app.tasks.evaluate_proposal",
        args=[app_id],
        queue="pdf_queue",
    )

    return {"application_id": app_id, "status": "submitted"}


# -------------------------------------------------
# GET OWN APPLICATION + SCORES  (NEW)
#
# Lets a bidder poll their proposal status and see scores
# once the Celery worker has evaluated it.
#
# Response while pending  → status: "submitted",  all scores 0.0
# Response after scoring  → status: "evaluated",  scores populated
# -------------------------------------------------
@router.get("/applications/{application_id}")
def get_my_application(
    application_id: int,
    user: User = Depends(require_applicant),
):
    with get_session() as session:
        app = session.get(Application, application_id)

        # 404 if not found
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")

        # Bidders can only see their own applications
        if user.id is None:
            raise HTTPException(status_code=500, detail="Authenticated user has no ID")
        user_id = user.id

        if app.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not your application")

        tender = session.get(Tender, app.tender_id)

        # Check if this application is the current best on the tender
        is_winner = (
            tender is not None
            and tender.best_proposal_id == app.id
        )

        # Scores are 0.0 while status == "submitted" (Celery not done yet).
        # Once status == "evaluated" all four fields are populated.
        evaluated = app.status == "evaluated"

        return {
            "application_id": app.id,
            "tender_id": app.tender_id,
            "tender_title": tender.title if tender else "Unknown",
            "status": app.status,
            # ── score block ───────────────────────────────────────────────
            "scores": {
                "overall":    app.overall_score,
                "technical":  app.technical_score,
                "pricing":    app.pricing_score,
                "compliance": app.compliance_score,
            },
            "score_summary": app.score_summary,
            "evaluated": evaluated,
            "is_winner": is_winner,
            # ── helpful hint for the frontend ─────────────────────────────
            # If not yet evaluated, the frontend can poll again after a delay.
            "message": (
                "Evaluation complete."
                if evaluated
                else "Your proposal is being evaluated. Check back shortly."
            ),
        }


# -------------------------------------------------
# ACCEPTED APPLICATIONS  (no change)
# -------------------------------------------------
@router.get("/accepted")
def applicant_accepted(user: User = Depends(require_applicant)):
    if user.id is None:
        raise HTTPException(status_code=500, detail="Authenticated user has no ID")
    user_id = user.id

    with get_session() as session:
        apps = session.exec(
            select(Application)
            .where(Application.user_id == user_id)
            .where(Application.status == "accepted")
        ).all()

        result = []
        for a in apps:
            tender = session.get(Tender, a.tender_id)
            result.append({
                "application_id": a.id,
                "tender_title": tender.title if tender else "Unknown",
                "status": a.status,
                "offer": json.loads(a.offer_json) if a.offer_json else None,
            })

        return result


# -------------------------------------------------
# RESPOND TO OFFER  (no change)
# -------------------------------------------------
@router.post("/offer/{application_id}/respond")
def respond_to_offer(
    application_id: int,
    decision: Optional[str] = None,
    data: Optional[dict] = Body(default=None),
    user: User = Depends(require_applicant),
):
    action = (data or {}).get("action") or decision
    if action not in ("accept", "reject"):
        raise HTTPException(400, "action must be 'accept' or 'reject'")

    if user.id is None:
        raise HTTPException(status_code=500, detail="Authenticated user has no ID")
    user_id = user.id

    with get_session() as session:
        app = session.get(Application, application_id)
        if not app:
            raise HTTPException(404, "Application not found")
        if app.user_id != user_id:
            raise HTTPException(403, "Not your application")
        if app.status != "offered":
            raise HTTPException(400, "No pending offer on this application")

        app.status = "accepted" if action == "accept" else "rejected"
        session.commit()

        return {"application_id": app.id, "status": app.status}


# -------------------------------------------------
# NOTIFICATIONS  (no change)
# -------------------------------------------------
@router.get("/notifications")
def applicant_notifications(user: User = Depends(require_applicant)):
    if user.id is None:
        raise HTTPException(status_code=500, detail="Authenticated user has no ID")
    user_id = user.id

    with get_session() as session:
        apps = session.exec(
            select(Application)
            .where(Application.user_id == user_id)
            .where(Application.status == 'offered')  # only pending offers
        ).all()

        notifications = []
        for a in apps:
            tender = session.get(Tender, a.tender_id)
            tender_title = tender.title if tender else "Unknown"

            if a.status == "offered":
                msg = f"You have received an offer for '{tender_title}'"
            elif a.status == "accepted":
                msg = f"Your acceptance for '{tender_title}' was confirmed"
            elif a.status == "rejected":
                msg = f"Your offer for '{tender_title}' was declined"
            elif a.status == "evaluated":
                msg = (
                    f"Your proposal for '{tender_title}' has been scored: "
                    f"{a.overall_score:.0f}/100"
                )
            else:
                msg = f"Update on your application for '{tender_title}'"

            notifications.append({
                "application_id": a.id,
                "tender_id": a.tender_id,
                "tender_title": tender_title,
                "status": a.status,
                "offer": json.loads(a.offer_json) if a.offer_json else None,
                "message": msg,
            })

        return notifications