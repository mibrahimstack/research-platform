"""
ingestion/upload_processor.py

Extracts and chunks text from user-uploaded PDF or DOCX files, so they
can be added to the vector store and knowledge graph alongside the
original Europe PMC corpus. This closes a real gap from the original
case study, which explicitly lists PDF and DOCX as required import
formats — until now, the pipeline only ever handled Europe PMC's XML
format.
"""

import re
from pypdf import PdfReader
from docx import Document as DocxDocument


def clean_whitespace(text):
    return re.sub(r"\s+", " ", text).strip()


def extract_text_from_pdf(file_obj):
    reader = PdfReader(file_obj)
    pages_text = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text:
            pages_text.append(text)
    return clean_whitespace(" ".join(pages_text))


def extract_text_from_docx(file_obj):
    doc = DocxDocument(file_obj)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return clean_whitespace(" ".join(paragraphs))


def extract_text(file_obj, filename):
    """Dispatches to the right extractor based on file extension."""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return extract_text_from_pdf(file_obj)
    elif lower.endswith(".docx"):
        return extract_text_from_docx(file_obj)
    elif lower.endswith(".txt"):
        return clean_whitespace(file_obj.read().decode("utf-8", errors="ignore"))
    else:
        raise ValueError(
            f"Unsupported file type: {filename}. Please upload a PDF, DOCX, or TXT file."
        )


def chunk_text(text, chunk_size=500, overlap=50):
    """Same chunking approach used for the rest of the corpus — ~500
    word chunks with overlap so context isn't lost at boundaries."""
    words = text.split()
    if not words:
        return []
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))
        start += chunk_size - overlap
    return chunks


def process_uploaded_file(file_obj, filename, title=None):
    """
    Full pipeline for one uploaded file: extract text, chunk it, and
    return records matching the same shape used throughout the rest of
    the project (paper_id, paper_title, section, chunk_index, text) —
    so an uploaded document can be added to the vector store and
    knowledge graph the exact same way as any other paper.
    """
    text = extract_text(file_obj, filename)
    chunks = chunk_text(text)

    safe_name = filename.rsplit(".", 1)[0].replace(" ", "_")
    paper_id = f"UPLOAD_{safe_name}"[:64]
    paper_title = title or filename

    records = []
    for i, chunk in enumerate(chunks):
        records.append({
            "paper_id": paper_id,
            "paper_title": paper_title,
            "section": "Uploaded Document",
            "chunk_index": i,
            "text": chunk,
        })
    return records
