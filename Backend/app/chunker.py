# backend/app/chunker.py

from typing import List
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def chunk_tender(
    text: str,
    tender_id: int,
    tender_title: str = "",
    chunk_size: int = 500,
    chunk_overlap: int = 100,
) -> List[Document]:
    """
    Split tender text into overlapping chunks.
    Each chunk is a LangChain Document with metadata attached.

    Metadata stored per chunk:
        tender_id    : int   — FK back to the Tender row
        tender_title : str   — human-readable label for retrieval context
        chunk_index  : int   — position in the original text (0-based)
        total_chunks : int   — total chunks produced from this tender
        source       : str   — always "tender" so you can filter in RAG
        char_start   : int   — approximate character offset in original text
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        # These separators let the splitter prefer natural boundaries
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    raw_chunks: List[str] = splitter.split_text(text)

    documents: List[Document] = []
    char_cursor = 0

    for idx, chunk_text in enumerate(raw_chunks):
        # Approximate char_start: find this chunk in the remaining text
        offset = text.find(chunk_text, char_cursor)
        char_start = offset if offset != -1 else char_cursor

        doc = Document(
            page_content=chunk_text,
            metadata={
                "tender_id": tender_id,
                "tender_title": tender_title,
                "chunk_index": idx,
                "total_chunks": len(raw_chunks),
                "source": "tender",
                "char_start": char_start,
            },
        )
        documents.append(doc)
        char_cursor = char_start + len(chunk_text)

    return documents
