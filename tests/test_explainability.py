from rag.answer import build_explained_answer, split_answer_sections


def test_build_explained_answer_includes_sources():
    results = {
        "documents": [["Some evidence text"]],
        "metadatas": [[{"paper_title": "Paper A", "section": "Abstract"}]],
        "distances": [[0.1]],
    }

    explained = build_explained_answer("This is the answer.", results)

    assert "This is the answer." in explained
    assert "Sources used:" in explained
    assert "Paper A" in explained
    assert "Abstract" in explained


def test_split_answer_sections_parses_body_and_sources():
    answer = "This is the answer.\n\nSources used:\n[1] Paper A (Abstract)\n[2] Paper B (Methods)"

    body, sources = split_answer_sections(answer)

    assert body == "This is the answer."
    assert sources == ["[1] Paper A (Abstract)", "[2] Paper B (Methods)"]
