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
    assert calls[0][1]["think"] is False
    assert calls[0][1]["options"]["num_predict"] == 1024
    assert "minimal JSON execution plan" in calls[0][1]["prompt"]


def test_detailed_style_changes_only_the_reviewed_prompt(monkeypatch) -> None:
    payloads = []

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def post(self, url, json):
            payloads.append(json)
            return httpx.Response(200, json={"response": '{"steps":[{"description":"Read brief","tool_name":"read_file","args":{"path":"brief.md"},"dependencies":[]}]}'}, request=httpx.Request("POST", url))

    monkeypatch.setattr("app.ollama.httpx.Client", FakeClient)
    steps = generate_plan("Read notes", [], ["read_file"], "http://127.0.0.1:11434", "test-model", available_files=["brief.md"], planning_style="detailed")
    assert steps[0].args == {"path": "brief.md"}
    assert "detailed but bounded" in payloads[0]["prompt"]
    assert "Do not provide shell commands" in payloads[0]["prompt"]


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


def test_ollama_repairs_unavailable_input_path(monkeypatch) -> None:
    prompts = []

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def post(self, url, json):
            prompts.append(json["prompt"])
            path = "invented.md" if len(prompts) == 1 else "brief.md"
            body = {"steps": [{"description": "Read selected notes", "tool_name": "read_file", "args": {"path": path}, "dependencies": []}]}
            return httpx.Response(200, json={"response": __import__("json").dumps(body)}, request=httpx.Request("POST", url))

    monkeypatch.setattr("app.ollama.httpx.Client", FakeClient)
    steps = generate_plan("Read notes", [], ["read_file"], "http://127.0.0.1:11434", "test-model", available_files=["brief.md"])
    assert steps[0].args["path"] == "brief.md"
    assert len(prompts) == 2
    assert 'Available input files: ["brief.md"]' in prompts[0]


def test_ollama_rejects_unavailable_input_path_after_repair(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def post(self, url, json):
            body = {"steps": [{"description": "Read invented notes", "tool_name": "read_file", "args": {"path": "invented.md"}, "dependencies": []}]}
            return httpx.Response(200, json={"response": __import__("json").dumps(body)}, request=httpx.Request("POST", url))

    monkeypatch.setattr("app.ollama.httpx.Client", FakeClient)
    with pytest.raises(ModelPlanInvalid, match="valid permitted plan"):
        generate_plan("Read notes", [], ["read_file"], "http://127.0.0.1:11434", "test-model", available_files=["brief.md"])


def test_ollama_reports_bounded_planning_timeout(monkeypatch) -> None:
    class TimeoutClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def post(self, url, json):
            raise httpx.ReadTimeout("slow model", request=httpx.Request("POST", url))

    monkeypatch.setattr("app.ollama.httpx.Client", TimeoutClient)
    with pytest.raises(ModelUnavailable, match="timed out after 45 seconds"):
        generate_plan("Read notes", [], ["read_file"], "http://127.0.0.1:11434", "test-model", 45)
