"""
ingestion/parse_paper.py

Step 1 of the pipeline: take one downloaded paper (Europe PMC full-text XML)
and turn it into clean, structured chunks of text ready for embedding
and entity extraction later.

Run this file directly to test it on ONE paper before wiring it into
anything else:

    python ingestion/parse_paper.py data/papers/PMC1234567.xml
"""

import sys
import re
from pathlib import Path

from lxml import etree

try:
    from docx import Document as DocxDocument
except ImportError:  # pragma: no cover - optional dependency in some environments
    DocxDocument = None

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - optional dependency in some environments
    PdfReader = None


def parse_paper_file(filepath):
    """Parse a paper from XML, DOCX, or PDF input."""
    path = Path(filepath)
    suffix = path.suffix.lower()

    if suffix == ".xml":
        return parse_paper_xml(path)
    if suffix == ".docx":
        return parse_docx(path)
    if suffix == ".pdf":
        return parse_pdf(path)

    raise ValueError(f"Unsupported paper format: {suffix}")


def parse_paper_xml(filepath):
    """
    Reads a Europe PMC full-text XML file and extracts:
      - title
      - abstract
      - body text, section by section

    Returns a dict: {"title": ..., "abstract": ..., "sections": [{"heading": ..., "text": ...}, ...]}
    """
    tree = etree.parse(filepath)
    root = tree.getroot()

    # Title
    title_el = root.find(".//article-title")
    title = "".join(title_el.itertext()).strip() if title_el is not None else "Untitled"

    # Abstract
    abstract_el = root.find(".//abstract")
    abstract = "".join(abstract_el.itertext()).strip() if abstract_el is not None else ""
    abstract = clean_whitespace(abstract)

    # Body — walk through each <sec> (section) in the article body
    sections = []
    body_el = root.find(".//body")
    if body_el is not None:
        for sec in body_el.findall(".//sec"):
            heading_el = sec.find("title")
            heading = "".join(heading_el.itertext()).strip() if heading_el is not None else "Untitled Section"

            # Grab all paragraph text inside this section (not nested subsections, to avoid duplicates)
            paragraphs = sec.findall("p")
            text = " ".join("".join(p.itertext()) for p in paragraphs)
            text = clean_whitespace(text)

            if text:  # skip empty sections
                sections.append({"heading": heading, "text": text})

    return {"title": title, "abstract": abstract, "sections": sections}


def parse_docx(filepath):
    """Extract text from a DOCX file into a simple paper structure."""
    if DocxDocument is None:
        raise ImportError("python-docx is required for DOCX ingestion")

    document = DocxDocument(filepath)
    paragraphs = [p.text.strip() for p in document.paragraphs if p.text and p.text.strip()]

    heading = None
    for paragraph in paragraphs:
        if paragraph.lower().startswith("heading"):
            continue
        if paragraph and len(paragraph.split()) <= 12:
            heading = paragraph
            break

    title = heading or (paragraphs[0] if paragraphs else "Untitled")
    text = " ".join(paragraphs)

    sections = []
    if text:
        sections.append({"heading": "Body", "text": clean_whitespace(text)})

    return {"title": title, "abstract": "", "sections": sections}


def parse_pdf(filepath):
    """Extract text from a PDF file into a simple paper structure."""
    if PdfReader is None:
        raise ImportError("pypdf is required for PDF ingestion")

    reader = PdfReader(str(filepath))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(page for page in pages if page).strip()

    title = "Untitled"
    if text:
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        if first_line:
            title = first_line

    sections = []
    if text:
        sections.append({"heading": "Body", "text": clean_whitespace(text)})

    return {"title": title, "abstract": "", "sections": sections}


def clean_whitespace(text):
    """Collapse repeated whitespace/newlines into single spaces."""
    return re.sub(r"\s+", " ", text).strip()


def chunk_text(text, chunk_size=500, overlap=50):
    """
    Splits text into word-based chunks of ~chunk_size words, with
    `overlap` words repeated between consecutive chunks so context
    isn't lost at chunk boundaries. This is what actually gets embedded
    later for retrieval.
    """
    words = text.split()
    if not words:
        return []

    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap  # move forward, but re-include the overlap

    return chunks


def paper_to_chunks(parsed_paper):
    """
    Takes the dict from parse_paper_xml() and produces a flat list of
    chunks, each tagged with which section it came from. This is the
    final output that will get embedded in the next pipeline step.
    """
    all_chunks = []

    if parsed_paper["abstract"]:
        for chunk in chunk_text(parsed_paper["abstract"]):
            all_chunks.append({"section": "Abstract", "text": chunk})

    for sec in parsed_paper["sections"]:
        for chunk in chunk_text(sec["text"]):
            all_chunks.append({"section": sec["heading"], "text": chunk})

    return all_chunks


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python ingestion/parse_paper.py <path_to_paper.xml>")
        sys.exit(1)

    filepath = sys.argv[1]
    parsed = parse_paper_file(filepath)

    print(f"Title: {parsed['title']}\n")
    print(f"Abstract ({len(parsed['abstract'].split())} words):")
    print(parsed["abstract"][:300] + "...\n")

    print(f"Found {len(parsed['sections'])} sections:")
    for sec in parsed["sections"]:
        print(f"  - {sec['heading']} ({len(sec['text'].split())} words)")

    chunks = paper_to_chunks(parsed)
    print(f"\nTotal chunks produced: {len(chunks)}")
    print(f"\nFirst chunk preview:\n{chunks[0]['text'][:300]}..." if chunks else "No chunks produced.")