from nlp.extract_claims import PROMPT, normalize_claims


def test_claim_prompt_formats_without_key_error():
    rendered = PROMPT.format(text="Example evidence")

    assert '"claims"' in rendered
    assert "Example evidence" in rendered


def test_normalize_claims_keeps_exact_evidence_span():
    chunk = {
        "paper_id": "PMC1", "chunk_index": 2,
        "text": "Metformin reduced HbA1c by 1.2% in the intervention group.",
    }
    records = normalize_claims([{
        "statement": "Metformin reduced HbA1c.", "claim_type": "effect",
        "direction": "beneficial", "confidence": 0.91,
        "evidence_quote": "Metformin reduced HbA1c by 1.2%",
    }], chunk)

    assert len(records) == 1
    assert records[0]["chunk_id"] == "PMC1:2"
    assert chunk["text"][records[0]["char_start"]:records[0]["char_end"]] == records[0]["evidence_quote"]


def test_normalize_claims_rejects_non_verbatim_evidence():
    chunk = {"paper_id": "PMC1", "chunk_index": 2, "text": "Metformin reduced HbA1c by 1.2%."}
    records = normalize_claims([{
        "statement": "Metformin reduced HbA1c.", "evidence_quote": "Metformin improves HbA1c.",
    }], chunk)

    assert records == []
