from dashboard.app import split_answer_sections


def test_split_answer_sections_handles_simple_reply():
    body, sources = split_answer_sections("Answer body\n\nSources used:\n[1] Paper A (Abstract)")

    assert body == "Answer body"
    assert sources == ["[1] Paper A (Abstract)"]
