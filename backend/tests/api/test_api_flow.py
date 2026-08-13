"""Integracyjne testy API (SQLite + sędzia Python)."""

from uuid import UUID

from fastapi.testclient import TestClient

from ksi.domain.entities import Task, User


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


def test_submit_and_accept(
    client: TestClient,
    sample_user: User,
    sample_task: Task,
) -> None:
    code = "import sys\nprint(sys.stdin.read(), end='')\n"
    # TestClient wykonuje BackgroundTasks synchronicznie przed zwróceniem odpowiedzi.
    r = client.post(
        f"/tasks/{sample_task.id}/submissions",
        json={"user_id": str(sample_user.id), "source_code": code, "language": "python"},
    )
    assert r.status_code == 201
    sub_id = r.json()["id"]

    detail = client.get(f"/submissions/{sub_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "accepted"
    # Hidden test still counts toward score, but is not returned in detail.
    assert body["score"] == 2
    assert body["max_score"] == 2
    assert len(body["test_results"]) == 1

    public = body["test_results"][0]
    assert public["visibility"] == "public"
    assert public["ordinal"] == 1
    assert public["input"] == "hello\n"
    assert public["actual_output"] is not None
    assert all(tr["visibility"] == "public" for tr in body["test_results"])


def test_submit_wrong_answer(
    client: TestClient,
    sample_user: User,
    sample_task: Task,
) -> None:
    r = client.post(
        f"/tasks/{sample_task.id}/submissions",
        json={
            "user_id": str(sample_user.id),
            "source_code": "print('nope')\n",
            "language": "python",
        },
    )
    assert r.status_code == 201
    sub_id = r.json()["id"]
    body = client.get(f"/submissions/{sub_id}").json()
    assert body["status"] == "wrong_answer"
    assert body["score"] == 0


def test_task_ranking_after_accept(
    client: TestClient,
    sample_user: User,
    sample_task: Task,
) -> None:
    code = "import sys\nprint(sys.stdin.read(), end='')\n"
    client.post(
        f"/tasks/{sample_task.id}/submissions",
        json={"user_id": str(sample_user.id), "source_code": code, "language": "python"},
    )

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
                    "points": 1,
                }
            ],
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["slug"] == "sum-ab"
    assert UUID(data["id"])
    assert len(data["public_tests"]) == 1
