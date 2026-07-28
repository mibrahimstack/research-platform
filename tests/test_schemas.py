import pytest
from pydantic import ValidationError

from api.schemas import AnswerResponse, QueryRequest, SourceChunk


def test_query_request_accepts_valid_values():
    request = QueryRequest(query="What is the effect of the drug?", top_k=3)

    assert request.query == "What is the effect of the drug?"
    assert request.top_k == 3


def test_query_request_rejects_too_short_query():
    with pytest.raises(ValidationError):
        QueryRequest(query="ok")


def test_answer_response_builds_expected_payload():
    payload = AnswerResponse(
        query="test",
        answer="answer",
        sources=[SourceChunk(paper_title="Paper", section="Abstract", text="text")],
    )

    assert payload.query == "test"
    assert payload.answer == "answer"
    assert payload.sources[0].paper_title == "Paper"
