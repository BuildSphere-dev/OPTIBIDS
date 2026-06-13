from fastapi import APIRouter
from sqlmodel import select
from typing import cast
from fastapi.responses import FileResponse

from .models import Tender
from .db import get_session

router = APIRouter()



@router.get("/tenders")
def list_tenders():
    with get_session() as session:
        tenders = session.exec(select(Tender)).all()

        return [
            {
                "id": cast(int, t.id),
                "title": t.title,
                "description": t.description,
                "status": t.status,
            }
            for t in tenders
        ]



@router.get("/download/{filename}")
def download_file(filename: str):
    file_path = f"/app/out/{filename}"
    return FileResponse(
        path=file_path,
        filename=filename,
    )
