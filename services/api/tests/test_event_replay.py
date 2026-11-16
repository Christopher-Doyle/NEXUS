import asyncio
import json

from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine
from app.models import Event, Task
from app.operations import task_events, task_journal


def test_sse_replays_after_last_event_id(tmp_path, monkeypatch) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'events.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        task = Task(goal="Replay events", state="draft")
        db.add(task)
        db.flush()
        db.add_all([
            Event(task_id=task.id, kind="created", payload_json="{}", correlation_id="one"),
            Event(task_id=task.id, kind="planned", payload_json='{"steps":1}', correlation_id="two"),
        ])
        db.commit()
        task_id = task.id
    monkeypatch.setattr("app.operations.SessionLocal", factory)

    async def first_chunk():
        with factory() as db:
            response = task_events(task_id, db, after=0, last_event_id="1")
            chunk = await anext(response.body_iterator)
            await response.body_iterator.aclose()
            return chunk

    chunk = asyncio.run(first_chunk())
    assert chunk.startswith("id: 2\nevent: update\ndata: ")
    payload = json.loads(chunk.split("data: ", 1)[1])
    assert payload["type"] == "planned"
    assert payload["payload"] == {"steps": 1}
    engine.dispose()


def test_journal_cursor_reads_events_beyond_first_page(tmp_path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'journal.db'}")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        task = Task(goal="Long journal", state="draft")
        db.add(task)
        db.flush()
        db.add_all(Event(task_id=task.id, kind="update", payload_json="{}", correlation_id="test") for _ in range(501))
        db.commit()
        first = task_journal(task.id, db, after=0)
        second = task_journal(task.id, db, after=first[-1]["id"])
        assert len(first) == 500
        assert len(second) == 1
        assert second[0]["id"] > first[-1]["id"]
    engine.dispose()
