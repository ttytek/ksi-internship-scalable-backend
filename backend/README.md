# KSI backend

FastAPI — użytkownicy, zadania, zgłoszenia, ranking. **Nie uruchamia kodu użytkownika.** Sędzia żyje w `../checker`.

Postgres należy do tego serwisu (schemat, Alembic, `ensure_schema`, rola `ksi_checker`).

## Encje

| Model | Tabela | Opis |
|-------|--------|------|
| **User** | `users` | Login po username. |
| **Task** | `tasks` | Zadanie; proste testy albo sprawdzarka. |
| **TaskTest** | `task_tests` | Przypadek (`public` w DB / `hidden` w packu S3). |
| **TaskTestPackRevision** | `task_test_pack_revisions` | Rewizja zipa. |
| **Submission** | `submissions` | Zgłoszenie; `queued` aż checker weźmie claim. |
| **TestResult** | `test_results` | Wynik testu. |

`POST /tasks/{id}/submissions` zapisuje `queued` i robi `XADD` na Redis Stream. Gdy Redis leży, i tak zwraca **201**; checker-sweeper dowiezie id później.

## API (skrót)

| Metoda | Ścieżka | Opis |
|--------|---------|------|
| GET | `/health` | Healthcheck |
| POST | `/users/login` | Login lub rejestracja po username |
| GET | `/tasks` | Lista opublikowanych zadań |
| GET | `/tasks/{id}` | Treść + testy publiczne |
| POST | `/tasks/{id}/submissions` | Kolejka zgłoszenia |
| GET | `/submissions/{id}` | Szczegóły + publiczne wyniki |
| GET | `/tasks/{id}/ranking` | Ranking zadania |
| GET | `/ranking` | Ranking globalny |

## Lokalnie

Z katalogu głównego repo: `docker compose up -d db redis`, potem:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn ksi.main:app --reload --app-dir src
```

`DATABASE_URL` i `REDIS_URL` — zob. `.env.example`.

```bash
make test
make lint
```
