import hashlib
import json
from collections.abc import Generator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base, get_db, make_engine
from app.main import app
from app.models import Approval, Execution, PlanStep, Task, utc_now
from app.network_policy import (
    FetchDenied,
    PinnedHTTPSConnection,
    fetch_https_text,
    public_addresses,
    validated_https_url,
)
from app.planning import args_hash
from app.tool_policy import ToolDenied, approval_scope
from app.tool_runner import report_bytes
from app.worker import run_once


@pytest.mark.parametrize("url", [
    "http://example.com/", "https://localhost/", "https://example.com:8443/",
    "https://user:pass@example.com/", "https://example.com/#secret",
    "https://example.com\\@127.0.0.1/", "https://example.com/\nHost: evil",
])
def test_only_unambiguous_https_urls_are_accepted(url) -> None:
    with pytest.raises(FetchDenied):
        validated_https_url(url)


def test_dns_rejects_any_private_answer(monkeypatch) -> None:
    monkeypatch.setattr("app.network_policy.socket.getaddrinfo", lambda *_args, **_kwargs: [
        (None, None, None, None, ("93.184.215.14", 443)),
        (None, None, None, None, ("127.0.0.1", 443)),
    ])
    with pytest.raises(FetchDenied, match="non-public"):
        public_addresses("example.com")


def test_pinned_connection_uses_resolved_ip_and_original_tls_name(monkeypatch) -> None:
    calls = []

    class Socket:
        def close(self):
            pass

    class Context:
        def wrap_socket(self, sock, server_hostname):
            calls.append(("tls", server_hostname))
            return sock

    monkeypatch.setattr("app.network_policy.ssl.create_default_context", Context)
    monkeypatch.setattr("app.network_policy.socket.create_connection", lambda target, timeout: (calls.append(("tcp", target, timeout)) or Socket()))
    connection = PinnedHTTPSConnection("example.com", "93.184.215.14")
    connection.connect()
    assert calls == [("tcp", ("93.184.215.14", 443), 3), ("tls", "example.com")]
    connection.close()


def test_fetch_pins_public_dns_and_revalidates_redirect(monkeypatch) -> None:
    connections = []

    class Response:
        status = 200

        def getheader(self, name):
            return {"Content-Type": "text/plain", "Content-Length": "5"}.get(name)

        def read(self, _limit):
            return b"Notes"

    class Connection:
        def __init__(self, host, address):
            connections.append((host, address))

        def request(self, method, path, headers):
            assert method == "GET"
            assert path == "/notes"
            assert headers["Accept-Encoding"] == "identity"

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr("app.network_policy.socket.getaddrinfo", lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.215.14", 443))])
    monkeypatch.setattr("app.network_policy.PinnedHTTPSConnection", Connection)
    assert fetch_https_text("https://example.com/notes") == ("https://example.com/notes", "Notes")
    assert connections == [("example.com", "93.184.215.14")]

    class Redirect(Response):
        status = 302

        def getheader(self, name):
            return "/private" if name == "Location" else None

    monkeypatch.setattr(Connection, "getresponse", lambda self: Redirect())
    addresses = iter(["93.184.215.14", "127.0.0.1"])
    monkeypatch.setattr("app.network_policy.socket.getaddrinfo", lambda *_args, **_kwargs: [(None, None, None, None, (next(addresses), 443))])
    with pytest.raises(FetchDenied, match="non-public"):
        fetch_https_text("https://example.com/notes")


def test_fetch_rejects_oversized_response(monkeypatch) -> None:
    class Response:
        status = 200

        def getheader(self, name):
            return "text/plain" if name == "Content-Type" else None

        def read(self, limit):
            return b"x" * limit

    class Connection:
        def __init__(self, _host, _address):
            pass

        def request(self, *_args, **_kwargs):
            pass

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr("app.network_policy.socket.getaddrinfo", lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.215.14", 443))])
    monkeypatch.setattr("app.network_policy.PinnedHTTPSConnection", Connection)
    with pytest.raises(FetchDenied, match="exceeds"):
        fetch_https_text("https://example.com/notes")


def test_fetch_rejects_cross_origin_redirect(monkeypatch) -> None:
    class Response:
        status = 302

        def getheader(self, name):
            return "https://other.example/notes" if name == "Location" else None

    class Connection:
        def __init__(self, _host, _address):
            pass

        def request(self, *_args, **_kwargs):
            pass

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr("app.network_policy.socket.getaddrinfo", lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.215.14", 443))])
    monkeypatch.setattr("app.network_policy.PinnedHTTPSConnection", Connection)
    with pytest.raises(FetchDenied, match="Cross-origin"):
        fetch_https_text("https://example.com/notes")


def test_network_tool_requires_task_grant_and_exact_approval(tmp_path, monkeypatch) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'network.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    url = "https://example.com/notes"
    calls = []
    monkeypatch.setattr("app.tool_runner.fetch_https_text", lambda value: (calls.append(value) or (value, "Public notes")))

    with factory() as db:
        denied = Task(goal="Deny ungranted network", state="queued", capabilities_json='["fetch_url"]', network_access=False, plan_version=1)
        allowed = Task(goal="Fetch approved public text", state="queued", capabilities_json='["fetch_url"]', network_access=True, plan_version=1)
        db.add_all([denied, allowed])
        db.flush()
        for task in (denied, allowed):
            db.add(PlanStep(task_id=task.id, ordinal=1, description="Fetch public text", tool_name="fetch_url", args_json='{"url":"https://example.com/notes"}', args_hash=args_hash({"url": url}), risk_level="high", state="pending"))
        db.commit()

    with factory() as db:
        assert run_once(db)
        assert db.get(Task, denied.id).state == "failed"
        assert not calls
        assert run_once(db)
        assert db.get(Task, allowed.id).state == "waiting_approval"
        approval = db.query(Approval).one()
        approval_id, scope = approval.id, approval.scope_hash
        assert not calls

    def test_db() -> Generator[Session, None, None]:
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    try:
        client = TestClient(app, base_url="http://127.0.0.1:8765")
        headers = {"x-nexus-intent": "local"}
        assert client.post(f"/api/v1/approvals/{approval_id}/decision", headers=headers, json={"decision": "approved", "scope_hash": "0" * 64}).status_code == 409
        assert client.post(f"/api/v1/approvals/{approval_id}/decision", headers=headers, json={"decision": "approved", "scope_hash": scope}).status_code == 200
    finally:
        app.dependency_overrides.clear()

    with factory() as db:
        assert run_once(db)
        assert db.get(Task, allowed.id).state == "completed"
        receipt = db.query(Execution).one()
        assert receipt.status == "completed"
        assert calls == [url]
    engine.dispose()


def test_report_cites_verified_https_receipt(tmp_path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'source.db'}")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        task = Task(goal="Summarize public text", state="running", capabilities_json='["fetch_url","write_report"]', network_access=True, plan_version=1)
        db.add(task)
        db.flush()
        url = "https://example.com/notes"
        step = PlanStep(task_id=task.id, ordinal=1, description="Fetch public text", tool_name="fetch_url", args_json=json.dumps({"url": url}), args_hash=args_hash({"url": url}), risk_level="high", state="completed")
        db.add(step)
        db.flush()
        content = "Public evidence"
        result = {"requested_url": url, "source": url, "content": content, "sha256": hashlib.sha256(content.encode()).hexdigest()}
        receipt = Execution(step_id=step.id, attempt=1, idempotency_key=approval_scope(task, step), status="completed", result_json=json.dumps(result))
        db.add(receipt)
        db.flush()
        report = report_bytes(db, task).decode()
        assert url in report
        assert content in report
        result["requested_url"] = "https://other.example/notes"
        receipt.result_json = json.dumps(result)
        db.flush()
        with pytest.raises(ToolDenied, match="provenance"):
            report_bytes(db, task)
    engine.dispose()


def test_approved_https_text_can_feed_an_approved_report(tmp_path, monkeypatch) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'fetch-report.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr("app.tool_runner.fetch_https_text", lambda url: (url, "Public report evidence"))
    monkeypatch.setattr("app.tool_runner.get_settings", lambda: type("Settings", (), {"data_dir": str(tmp_path / "data")})())
    with factory() as db:
        task = Task(goal="Create report from public HTTPS text", state="queued", capabilities_json='["fetch_url","write_report"]', network_access=True, plan_version=1)
        db.add(task)
        db.flush()
        url = "https://example.com/notes"
        db.add_all([
            PlanStep(task_id=task.id, ordinal=1, description="Fetch public notes", tool_name="fetch_url", args_json=json.dumps({"url": url}), args_hash=args_hash({"url": url}), risk_level="high", state="pending"),
            PlanStep(task_id=task.id, ordinal=2, description="Write cited report", tool_name="write_report", args_json='{"filename":"public-report.md"}', args_hash=args_hash({"filename": "public-report.md"}), risk_level="high", state="pending", dependencies_json="[1]"),
        ])
        db.commit()
        task_id = task.id

    def approve_pending() -> None:
        with factory() as db:
            approval = db.query(Approval).filter_by(decision="pending").one()
            approval_id, scope = approval.id, approval.scope_hash

        def test_db() -> Generator[Session, None, None]:
            with factory() as db:
                yield db

        app.dependency_overrides[get_db] = test_db
        try:
            client = TestClient(app, base_url="http://127.0.0.1:8765")
            response = client.post(f"/api/v1/approvals/{approval_id}/decision", headers={"x-nexus-intent": "local"}, json={"decision": "approved", "scope_hash": scope})
            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()

    with factory() as db:
        assert run_once(db)
    approve_pending()
    with factory() as db:
        assert run_once(db)
        assert db.get(Task, task_id).state == "running"
        assert run_once(db)
        assert db.get(Task, task_id).state == "waiting_approval"
    approve_pending()
    with factory() as db:
        assert run_once(db)
        assert db.get(Task, task_id).state == "completed"
        assert db.query(Execution).count() == 2
    report = (tmp_path / "data" / "artifacts" / task_id / "public-report.md").read_text(encoding="utf-8")
    assert "https://example.com/notes" in report
    assert "Public report evidence" in report
    engine.dispose()


def test_expired_https_lease_never_retries_uncertain_request(tmp_path, monkeypatch) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'uncertain-fetch.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    url = "https://example.com/notes"
    with factory() as db:
        task = Task(goal="Check uncertain HTTPS request", state="running", capabilities_json='["fetch_url"]', network_access=True, plan_version=1)
        db.add(task)
        db.flush()
        step = PlanStep(task_id=task.id, ordinal=1, description="Fetch public notes", tool_name="fetch_url", args_json=json.dumps({"url": url}), args_hash=args_hash({"url": url}), risk_level="high", state="running")
        db.add(step)
        db.flush()
        db.add(Execution(step_id=step.id, attempt=1, idempotency_key=approval_scope(task, step), status="running", lease_until=utc_now() - timedelta(seconds=1)))
        db.commit()
        task_id, step_id = task.id, step.id
    monkeypatch.setattr("app.worker.run_tool", lambda *_args: pytest.fail("Uncertain HTTPS request was retried"))
    with factory() as db:
        assert run_once(db)
        assert db.get(Task, task_id).state == "failed"
        assert db.get(PlanStep, step_id).state == "needs_review"
        assert db.query(Execution).one().status == "needs_review"
    engine.dispose()
