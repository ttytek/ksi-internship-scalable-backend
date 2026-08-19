"""Integracyjne testy API (SQLite, bez sędziego)."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ksi.domain.entities import Submission, Task, User
from ksi.domain.enums import SubmissionStatus
from ksi.services.queue import publish_submission


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_login_creates_user(client: TestClient) -> None:
    r1 = client.post("/users/login", json={"username": "bob"})
    assert r1.status_code == 200
    body = r1.json()
    assert body["username"] == "bob"
    user_id = body["id"]

    r2 = client.post("/users/login", json={"username": "bob"})
    assert r2.status_code == 200
    assert r2.json()["id"] == user_id


def test_list_and_get_task(client: TestClient, sample_task: Task) -> None:
    listed = client.get("/tasks")
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 1
    assert items[0]["slug"] == "echo"

    detail = client.get(f"/tasks/{sample_task.id}")
    assert detail.status_code == 200
    data = detail.json()
    assert data["title"] == "Echo"
    assert len(data["public_tests"]) == 1
    assert data["public_tests"][0]["input"] == "hello\n"


def test_submit_returns_queued(
    client: TestClient,
    sample_user: User,
    sample_task: Task,
) -> None:
    code = "import sys\nprint(sys.stdin.read(), end='')\n"
    r = client.post(
        f"/tasks/{sample_task.id}/submissions",
        json={"user_id": str(sample_user.id), "source_code": code, "language": "python"},
    )
    assert r.status_code == 201
    assert r.json()["status"] == "queued"
    sub_id = r.json()["id"]

    detail = client.get(f"/submissions/{sub_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "queued"
    assert body["test_results"] == []


def test_submit_calls_publish(
    client: TestClient,
    sample_user: User,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    published: list[UUID] = []
    monkeypatch.setattr(
        "ksi.api.routes.submissions.publish_submission",
        lambda sid: published.append(sid),
    )
    r = client.post(
        f"/tasks/{sample_task.id}/submissions",
        json={
            "user_id": str(sample_user.id),
            "source_code": "print(1)\n",
            "language": "python",
        },
    )
    assert r.status_code == 201
    assert published == [UUID(r.json()["id"])]


def test_publish_submission_swallows_redis_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class Boom:
        def xadd(self, *args: object, **kwargs: object) -> None:
            raise ConnectionError("redis down")

    monkeypatch.setattr("ksi.services.queue._redis", lambda: Boom())
    publish_submission(uuid4())


def test_task_ranking_after_accept(
    client: TestClient,
    sample_user: User,
    sample_task: Task,
    db_session: Session,
) -> None:
    db_session.add(
        Submission(
            task_id=sample_task.id,
            user_id=sample_user.id,
            source_code="print(1)\n",
            language="python",
            status=SubmissionStatus.ACCEPTED,
            score=1,
            max_score=1,
            judged_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    ranking = client.get(f"/tasks/{sample_task.id}/ranking")
    assert ranking.status_code == 200
    rows = ranking.json()
    assert len(rows) == 1
    assert rows[0]["username"] == "alice"
    assert rows[0]["rank"] == 1

    global_r = client.get("/ranking")
    assert global_r.status_code == 200
    assert global_r.json()[0]["solved_count"] == 1


def test_create_task_endpoint(client: TestClient) -> None:
    r = client.post(
        "/tasks",
        json={
            "slug": "sum-ab",
            "title": "Sum",
            "statement": "Dodaj dwie liczby.",
            "tests": [
                {
                    "visibility": "public",
                    "input": "1 2\n",
                    "expected_output": "3\n",
                    "points": 0,
                }
            ],
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["slug"] == "sum-ab"
    assert UUID(data["id"])
    assert len(data["public_tests"]) == 1
