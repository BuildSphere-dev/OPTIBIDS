# backend/app/models.py

from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship



class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    hashed_password: str
    role: str = Field(default="applicant")

    applications: List["Application"] = Relationship(back_populates="user")



class Tender(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    title: str
    description: str
    raw_text: str
    summary_json: Optional[str] = None
    status: str = "draft"
    files: Optional[str] = None

    best_proposal_id: Optional[int] = Field(default=None, foreign_key="application.id")
    best_score: float = Field(default=0.0)

    applications: List["Application"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Application.tender_id]"}
    )


class Application(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    tender_id: int = Field(foreign_key="tender.id")
    user_id: int = Field(foreign_key="user.id")

    applicant_text: str
    pdf_path: Optional[str] = None          # path to uploaded proposal PDF

    status: str = Field(default="submitted", index=True)
    offer_json: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)

    # ── Scoring fields (populated by Celery evaluate_proposal task) ─────────
    overall_score: float = Field(default=0.0)
    technical_score: float = Field(default=0.0)
    pricing_score: float = Field(default=0.0)
    compliance_score: float = Field(default=0.0)
    score_summary: Optional[str] = None     # 2-3 sentence LLM evaluation

    user: Optional["User"] = Relationship(back_populates="applications")



class TenderChunk(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    tender_id: int = Field(foreign_key="tender.id", index=True)

    # LangChain Document fields
    chunk_index: int                        # position in the original text
    total_chunks: int                       # total chunks for this tender
    chunk_text: str                         # page_content of the Document
    tender_title: str = Field(default="")  # metadata: human-readable label

    # Stored embedding as JSON list of floats (e.g. "[0.1, 0.4, ...]")
    # Populated by pipeline.index_tender at publish time.
    embedding_json: Optional[str] = None



class Requirement(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tender_id: int
    req_json: str
    confidence: float


class SKU(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sku_code: str
    description: str
    specs_json: Optional[str] = None
    price_base: float = 0.0


class Match(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tender_id: int
    sku_id: int
    score: float
    explanation: Optional[str] = None


class Pricing(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tender_id: int
    line_items: str
    total_amount: float
    margin_percent: float = 10.0
