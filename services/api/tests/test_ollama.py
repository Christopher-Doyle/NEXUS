import httpx
import pytest

from app.ollama import ModelPlanInvalid, ModelUnavailable, generate_plan, local_endpoint


def test_ollama_requires_local_endpoint_and_model() -> None:
    with pytest.raises(ValueError):
        local_endpoint("https://example.com")
    with pytest.raises(ModelUnavailable):
        generate_plan("Read notes", [], ["read_file"], "http://127.0.0.1:11434", "")


def test_ollama_repairs_once_then_validates(monkeypatch) -> None:
    calls = []
    valid = {"steps": [{"description": "Read the brief", "tool_name": "read_file", "args": {"path": "brief.md"}, "dependencies": []}]}

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def post(self, url, json):
            calls.append((url, json))
            response = "invalid" if len(calls) == 1 else __import__("json").dumps(valid)
            return httpx.Response(200, json={"response": response}, request=httpx.Request("POST", url))

    monkeypatch.setattr("app.ollama.httpx.Client", FakeClient)
    steps = generate_plan("Read notes", [], ["read_file"], "http://127.0.0.1:11434", "test-model")
    assert len(steps) == 1
    assert len(calls) == 2


def test_ollama_rejects_unsupported_tool_after_repair(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def post(self, url, json):
            body = {"steps": [{"description": "Run a shell", "tool_name": "shell", "args": {}, "dependencies": []}]}
            return httpx.Response(200, json={"response": __import__("json").dumps(body)}, request=httpx.Request("POST", url))

    monkeypatch.setattr("app.ollama.httpx.Client", FakeClient)
    with pytest.raises(ModelPlanInvalid):
        generate_plan("Run shell", [], ["read_file"], "http://127.0.0.1:11434", "test-model")
