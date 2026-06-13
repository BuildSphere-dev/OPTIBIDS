from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks
from sqlmodel import select
from typing import Optional
import os, uuid, json

from .db import get_session
from .auth_helpers import get_current_user
from .models import Tender, User, Application
from .pipeline import index_tender
from . import ai_agent


router = APIRouter()
UPLOAD_DIR = "/app/out"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def require_admin(user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(403, "Admin only")
    return user


@router.post("/tenders")
async def create_tender(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    description: str = Form(...),
    published: bool = Form(True),
    file: Optional[UploadFile] = File(None),
    admin: User = Depends(require_admin),
):
    files = []

    if file:
        fname = f"{uuid.uuid4()}_{file.filename}"
        with open(os.path.join(UPLOAD_DIR, fname), "wb") as f:
            f.write(await file.read())
        files.append(fname)

    with get_session() as session:
        tender = Tender(
            title=title,
            description=description,
            raw_text=description,
            status="public" if published else "draft",
            files=json.dumps(files),
        )
        session.add(tender)
        session.commit()
        session.refresh(tender)
        tender_id = tender.id

    if published and tender_id is not None:
        background_tasks.add_task(index_tender, tender_id)

    return {"id": tender_id}

@router.get("/tenders")
def admin_list_tenders(admin: User = Depends(require_admin)):
    with get_session() as session:
        tenders = session.exec(
            select(Tender).where(Tender.status == "public")
        ).all()

        out = []
        for t in tenders:
            count = session.exec(
                select(Application).where(Application.tender_id == t.id)
            ).all()

            out.append({
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "status": t.status,
                "applicant_count": len(count),
                "files": json.loads(t.files) if t.files else []
            })

        return out


@router.get("/applications")
def admin_list_applications(admin: User = Depends(require_admin)):
    with get_session() as session:
        apps = session.exec(select(Application)).all()
        users = {u.id: u for u in session.exec(select(User)).all()}
        tenders = {t.id: t for t in session.exec(select(Tender)).all()}

        result = []
        for a in apps:
            user = users.get(a.user_id)
            tender = tenders.get(a.tender_id)
            result.append({
                "id": a.id,
                "tender_id": a.tender_id,
                "user_email": user.email if user else "Unknown",
                "tender_title": tender.title if tender else "Unknown",
                "status": a.status or "submitted",
                "overall_score": a.overall_score,
                "technical_score": a.technical_score,
                "pricing_score": a.pricing_score,
                "compliance_score": a.compliance_score,
            })
        return result



@router.get("/applications/{application_id}")
def get_application(application_id: int, admin: User = Depends(require_admin)):
    with get_session() as session:
        app = session.get(Application, application_id)
        if not app:
            raise HTTPException(404, "Application not found")

        tender = session.get(Tender, app.tender_id)
        user = session.get(User, app.user_id)

        return {
            "id": app.id,
            "tender_id": app.tender_id,
            "tender_title": tender.title if tender else "Unknown",
            "user_email": user.email if user else "Unknown",
            "applicant_text": app.applicant_text,
            "status": app.status,
        }

@router.post("/tenders/{tender_id}/summary")
def summarize_tender(tender_id: int, admin: User = Depends(require_admin)):
    with get_session() as session:
        tender = session.get(Tender, tender_id)
        if not tender:
            raise HTTPException(status_code=404, detail="Tender not found")

        # Pure DB read — no Ollama call
        result = ai_agent.build_user_summary(tender_id, session)

        # Cache result on the Tender row (same behaviour as before)
        tender.summary_json = json.dumps(result)
        session.add(tender)
        session.commit()

    return result
# CHANGED — add BackgroundTasks parameter to trigger index_tender after response
# The route path, method, and response are IDENTICAL to what you had.
# If you already have a "create tender" endpoint, add `background_tasks`
# the same way and call background_tasks.add_task(index_tender, tender.id)
# right before the return statement.
#
# Example (adapt to your actual create/publish endpoint):
@router.post("/tenders/{tender_id}/publish")
def publish_tender(
    tender_id: int,
    background_tasks: BackgroundTasks,
    admin: User = Depends(require_admin),
):
    with get_session() as session:
        tender = session.get(Tender, tender_id)
        if not tender:
            raise HTTPException(status_code=404, detail="Tender not found")
        if tender.status not in ("draft", "indexing"):
            raise HTTPException(status_code=400, detail="Tender already published")

    # index_tender runs AFTER this response is sent — does not block the caller
    background_tasks.add_task(index_tender, tender_id)

    return {"tender_id": tender_id, "status": "indexing_started"}



@router.post("/applications/{application_id}/offer")
def send_offer(
    application_id: int,
    data: dict,
    admin: User = Depends(require_admin),
):
    message = data.get("message")
    if not isinstance(message, str) or not message.strip():
        raise HTTPException(400, "Offer message required")

    with get_session() as session:
        app = session.get(Application, application_id)
        if not app:
            raise HTTPException(404, "Application not found")

        app.status = "offered"
        app.offer_json = json.dumps({"message": message})
        session.commit()

        return {
            "status": "offered",
            "application_id": application_id
        }

@router.get("/accepted-offers")
def admin_accepted_offers(admin: User = Depends(require_admin)):
    with get_session() as session:
        rows = session.exec(
            select(Application, User, Tender)
            .where(Application.status == "accepted")
            .where(Application.user_id == User.id)
            .where(Application.tender_id == Tender.id)
        ).all()

        return [
            {
                "application_id": app.id,
                "applicant_email": user.email,
                "tender_title": tender.title,
                "offer": json.loads(app.offer_json) if app.offer_json else None,
                "status": app.status,
            }
            for app, user, tender in rows
        ]
