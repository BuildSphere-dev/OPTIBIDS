# backend/app/matcher.py
import faiss
import numpy as np
from typing import List
from pathlib import Path


INDEX_FILE = Path(__file__).resolve().parent / "faiss.index"
VECTOR_DIM = 16


def build_index(vectors: List[List[float]]) -> None:
    """
    Build FAISS index from a list of embedding vectors.
    """
    if not vectors:
        print("No vectors provided, FAISS index not created")
        return

    xb = np.array(vectors, dtype="float32")

    index = faiss.IndexFlatL2(VECTOR_DIM)  # type: ignore
    index.add(xb)                           # type: ignore[arg-type]

    faiss.write_index(index, str(INDEX_FILE))  # type: ignore
    print(f"FAISS index created at {INDEX_FILE}")


def load_index():
    if not INDEX_FILE.exists():
        raise FileNotFoundError(f"FAISS index not found at {INDEX_FILE}")

    return faiss.read_index(str(INDEX_FILE))


def search_index(query_vec: List[float], top_k: int = 3):
    index = load_index()

    q = np.array([query_vec], dtype="float32")
    D, I = index.search(q, top_k)

    return I[0].tolist(), D[0].tolist()
