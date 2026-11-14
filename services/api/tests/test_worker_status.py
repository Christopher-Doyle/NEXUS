from collections.abc import Generator
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base, get_db, make_engine
from app.main import app
from app.models import WorkerHeartbeat, utc_now


def test_worker_status_tracks_recent_heartbeat(tmp_path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'worker-status.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    def test_db() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    try:
        client = TestClient(app, base_url="http://127.0.0.1:8765")
        assert client.get("/api/v1/worker/status").json() == {
            "active": False, "active_count": 0, "last_seen_at": None,
        }
        with factory() as db:
            db.add(WorkerHeartbeat(id="stale", started_at=utc_now() - timedelta(minutes=1), last_seen_at=utc_now() - timedelta(minutes=1)))
            db.add(WorkerHeartbeat(id="fresh", started_at=utc_now(), last_seen_at=utc_now()))
            db.commit()
        status = client.get("/api/v1/worker/status").json()
        assert status["active"] is True
        assert status["active_count"] == 1
        assert status["last_seen_at"] is not None
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
