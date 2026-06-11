# backend/app/db.py
from sqlmodel import create_engine, SQLModel, Session
from pathlib import Path
from contextlib import contextmanager

# Use a path that's accessible from both backend and worker containers
# via shared volume at /app/data/
DB_FILE = Path("/app/data/database.db")
DB_FILE.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_FILE}", echo=False)

def init_db():
    SQLModel.metadata.create_all(engine)

@contextmanager
def get_session():
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()

