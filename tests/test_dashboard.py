import builtins
import importlib
import sys

from dashboard.app import split_answer_sections


def test_split_answer_sections_handles_simple_reply():
    body, sources = split_answer_sections("Answer body\n\nSources used:\n[1] Paper A (Abstract)")

    assert body == "Answer body"
    assert sources == ["[1] Paper A (Abstract)"]


def test_dashboard_imports_without_optional_ai_dependencies(monkeypatch):
    sys.modules.pop("dashboard.app", None)

    original_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name in {"agents.copilot", "rag.answer", "sentence_transformers", "transformers"}:
            raise ModuleNotFoundError(name)
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    module = importlib.import_module("dashboard.app")

    assert hasattr(module, "split_answer_sections")
