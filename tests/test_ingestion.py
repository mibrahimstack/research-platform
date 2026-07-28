from ingestion.parse_paper import parse_paper_xml, paper_to_chunks


def test_parse_paper_xml_returns_title_and_sections(fixtures_dir):
    parsed = parse_paper_xml(fixtures_dir / "sample_paper.xml")

    assert parsed["title"] == "Sample Paper"
    assert "new treatment for diabetes" in parsed["abstract"]
    assert parsed["sections"][0]["heading"] == "Introduction"
    assert "improve outcomes" in parsed["sections"][0]["text"]


def test_paper_to_chunks_creates_expected_chunks(fixtures_dir):
    parsed = parse_paper_xml(fixtures_dir / "sample_paper.xml")
    chunks = paper_to_chunks(parsed)

    assert len(chunks) >= 2
    assert any(chunk["section"] == "Abstract" for chunk in chunks)
    assert any(chunk["section"] == "Introduction" for chunk in chunks)
    assert all("text" in chunk for chunk in chunks)
