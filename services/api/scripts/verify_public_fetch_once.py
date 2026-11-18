"""One-shot public fetch verification; run only with fresh owner approval."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Generator
from pathlib import Path

URL = "https://example.com/"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-approved-once", action="store_true")
    args = parser.parse_args()
    if not args.owner_approved_once:
        parser.error("Fresh owner approval for one public HTTPS request is required")

    with tempfile.TemporaryDirectory(prefix="nexus-public-fetch-") as temporary:
        root = Path(temporary)
        os.environ["DATABASE_URL"] = f"sqlite:///{(root / 'nexus.db').as_posix()}"
        os.environ["DATA_DIR"] = str(root)
        os.environ["APPROVED_WORKSPACES"] = ""
        os.environ["OLLAMA_MODEL"] = ""
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)

        from fastapi.testclient import TestClient
        from sqlalchemy.orm import Session, sessionmaker

        from app.db import get_db, make_engine
        from app.main import app
        from app.network_policy import FetchDenied, PinnedHTTPSConnection
        from app.worker import run_once

        engine = make_engine(os.environ["DATABASE_URL"])
        factory = sessionmaker(bind=engine)

        def test_db() -> Generator[Session, None, None]:
            with factory() as db:
                yield db

        app.dependency_overrides[get_db] = test_db
        request_count = 0
        original_request = PinnedHTTPSConnection.request

        def only_one_request(self, *request_args, **request_kwargs):
            nonlocal request_count
            if request_count:
                raise FetchDenied("One-time verification request limit reached")
            request_count += 1
            return original_request(self, *request_args, **request_kwargs)

        PinnedHTTPSConnection.request = only_one_request
        try:
            client = TestClient(app, base_url="http://127.0.0.1:8765")
            headers = {"X-Nexus-Intent": "local"}

            def mutation(method: str, path: str, payload: dict | None = None) -> dict:
                response = client.request(method, path, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()

            task = mutation("POST", "/api/v1/tasks", {"goal": "Verify one approved public HTTPS fetch", "capabilities": ["read_file", "write_report", "fetch_url"], "network_access": True})
            task_id = task["id"]
            planned = mutation("POST", f"/api/v1/tasks/{task_id}/plan", {"mode": "demo"})
            mutation("PATCH", f"/api/v1/tasks/{task_id}/steps", {"plan_version": planned["plan_version"], "steps": [{"description": "Fetch the owner-approved example page", "tool_name": "fetch_url", "args": {"url": URL}, "dependencies": []}]})
            mutation("POST", f"/api/v1/tasks/{task_id}/start")
            with factory() as db:
                assert run_once(db)
            approvals = client.get("/api/v1/approvals").json()
            assert len(approvals) == 1 and approvals[0]["requested_action"] == f"Fetch HTTPS text from {URL}"
            assert request_count == 0, "No outbound request is allowed before approval"
            approval = approvals[0]
            mutation("POST", f"/api/v1/approvals/{approval['id']}/decision", {"decision": "approved", "scope_hash": approval["scope_hash"]})
            with factory() as db:
                assert run_once(db)
            final_task = client.get(f"/api/v1/tasks/{task_id}").json()
            receipts = client.get(f"/api/v1/tasks/{task_id}/executions").json()
            assert request_count == 1
            assert final_task["state"] == "completed", final_task["state"]
            assert len(receipts) == 1 and receipts[0]["status"] == "completed"
            assert receipts[0]["result"]["requested_url"] == URL
            assert receipts[0]["result"]["source"] == URL
            assert receipts[0]["result"].get("content") is None
            print(json.dumps({"task_state": final_task["state"], "approved_url": URL, "outbound_requests": request_count, "source": receipts[0]["result"]["source"], "sha256": receipts[0]["result"]["sha256"]}, indent=2))
        finally:
            PinnedHTTPSConnection.request = original_request
            app.dependency_overrides.clear()
            engine.dispose()


if __name__ == "__main__":
    main()
