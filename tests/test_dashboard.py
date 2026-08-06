from dashboard.app import build_graph_html


def test_build_graph_html_uses_api_graph_payload():
    html = build_graph_html({
        "nodes": [{"id": "p1", "label": "Paper", "name": "Paper title"}],
        "edges": [],
    })

    assert "Paper title" in html
