# KSI

Backend API (FastAPI) — prosta platforma do zadań programistycznych (styl LeetCode).

## Encje (modele ORM)

Modele SQLAlchemy 2 (`src/ksi/domain/entities.py`), sesja w `src/ksi/db/`:

| Model | Tabela | Opis |
|-------|--------|------|
| **User** | `users` | Użytkownik (bez ról / hasła — login po username). |
| **Task** | `tasks` | Zadanie; proste testy albo sprawdzarka. |
| **TaskTest** | `task_tests` | Przypadek testowy (`public` w DB / `hidden` w packu S3). |
| **TaskTestPackRevision** | `task_test_pack_revisions` | Rewizja zipa z testami głównymi. |
| **Submission** | `submissions` | Zgłoszenie rozwiązania; kolejka → ocena w tle. |
| **TestResult** | `test_results` | Wynik pojedynczego testu (werdykt, punkty, czas). |

## API (skrót)

| Metoda | Ścieżka | Opis |
|--------|---------|------|
| GET | `/health` | Healthcheck |
| POST | `/users/login` | Login lub rejestracja po username |
| POST | `/users` | Utwórz użytkownika (409 jeśli zajęty) |
| GET | `/tasks` | Lista opublikowanych zadań |
| GET | `/tasks/{id}` | Treść + testy publiczne |
| POST | `/tasks` | Utwórz zadanie z testami |
| POST | `/tasks/{id}/submissions` | Wyślij rozwiązanie (sędzia w tle) |
| GET | `/submissions/{id}` | Szczegóły + wyniki testów |
| GET | `/users/{id}/submissions` | Zgłoszenia użytkownika |
| GET | `/tasks/{id}/ranking` | Ranking zadania |
| GET | `/ranking` | Ranking globalny |

Sędzia MVP: tylko **Python** + tryb **simple** (porównanie stdout).

## Wymagania

- Python 3.12+
- Docker (opcjonalnie)

## Lokalnie

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Postgres
docker compose up -d db

uvicorn ksi.main:app --reload --app-dir src
```

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok"}
```

### Seed z datasetu

Problemy z `private_tests` / `generated_tests` wymagają skonfigurowanego S3
(`S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` — zob. `.env.example`).
Bez bucketa seed wypisze `ERR  …: S3 is not configured but this problem has private/generated tests`
(datasetowe `brcktsrm` itd. mają generated tests). Same przykłady publiczne seedują się bez S3.

```bash
# z katalogu backend, przy działającym Postgresie i uzupełnionych S3_*
python -m ksi.scripts.seed_dataset --dir ../dataset/problems
# lub: ksi-seed --dir ../dataset/problems
```

Nowa rewizja packa (bez kasowania starych testów i bez rejudge):

```bash
python -m ksi.scripts.attach_main_pack --slug brcktsrm --zip pack.zip
# lub: ksi-attach-pack --task-id <uuid> --zip pack.zip
```

Domyślny `DATABASE_URL`: `postgresql+psycopg://ksi:ksi@localhost:5432/ksi`

## Docker

```bash
docker compose up --build
```

- API: http://127.0.0.1:8000  
- Postgres: `localhost:5432` (user/hasło/baza: `ksi`)

## Testy

```bash
make test
make lint
```
