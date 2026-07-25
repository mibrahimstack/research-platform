"""
fetch_papers.py

Downloads open-access biomedical papers (metadata + full-text PDF/XML where
available) from Europe PMC for a given search topic. No API key needed.

Run locally on your own machine (this needs internet access to
www.ebi.ac.uk, which sandboxed dev environments may block).

Usage:
    pip install requests --break-system-packages   # or without the flag on your own machine
    python fetch_papers.py
"""

import requests
import time
import os
import json

# ---- CONFIG: change this to your chosen topic ----
QUERY = "type 2 diabetes AND drug therapy"
MAX_PAPERS = 100
OUTPUT_DIR = "data/papers"
# ----------------------------------------------------

BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def search_papers(query, max_results=100):
    """Search Europe PMC for open-access papers matching the query."""
    results = []
    page_size = 25
    cursor_mark = "*"

    while len(results) < max_results:
        params = {
            "query": f"({query}) AND OPEN_ACCESS:Y",
            "format": "json",
            "pageSize": page_size,
            "cursorMark": cursor_mark,
        }
        resp = requests.get(BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        hits = data.get("resultList", {}).get("result", [])
        if not hits:
            break

        results.extend(hits)
        cursor_mark = data.get("nextCursorMark", None)
        if not cursor_mark:
            break

        time.sleep(0.5)  # be polite to the API

    return results[:max_results]


def download_fulltext(pmcid, out_path):
    """Download full-text XML for a paper given its PMCID (e.g. 'PMC1234567')."""
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200 and resp.content:
            with open(out_path, "wb") as f:
                f.write(resp.content)
            return True
    except requests.RequestException:
        pass
    return False


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    metadata_path = os.path.join(OUTPUT_DIR, "metadata.jsonl")

    print(f"Searching Europe PMC for: {QUERY}")
    papers = search_papers(QUERY, MAX_PAPERS)
    print(f"Found {len(papers)} open-access papers")

    downloaded = 0
    with open(metadata_path, "w", encoding="utf-8") as meta_file:
        for i, paper in enumerate(papers, 1):
            pmcid = paper.get("pmcid")
            title = paper.get("title", "untitled")
            authors = paper.get("authorString", "")
            journal = paper.get("journalTitle", "")
            pub_year = paper.get("pubYear", "")
            doi = paper.get("doi", "")

            record = {
                "pmcid": pmcid,
                "title": title,
                "authors": authors,
                "journal": journal,
                "year": pub_year,
                "doi": doi,
            }
            meta_file.write(json.dumps(record) + "\n")

            if pmcid:
                out_path = os.path.join(OUTPUT_DIR, f"{pmcid}.xml")
                ok = download_fulltext(pmcid, out_path)
                if ok:
                    downloaded += 1
                    print(f"[{i}/{len(papers)}] Downloaded: {title[:70]}")
                else:
                    print(f"[{i}/{len(papers)}] No full text available: {title[:70]}")
                time.sleep(0.3)  # be polite to the API
            else:
                print(f"[{i}/{len(papers)}] No PMCID, skipping full text: {title[:70]}")

    print(f"\nDone. Downloaded {downloaded} full-text papers out of {len(papers)} found.")
    print(f"Metadata saved to: {metadata_path}")


if __name__ == "__main__":
    main()
