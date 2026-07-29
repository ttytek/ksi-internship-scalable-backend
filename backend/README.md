# KSI

Backend API (FastAPI).

## Encje (modele ORM)

Modele SQLAlchemy 2 (`src/ksi/domain/entities.py`), sesja w `src/ksi/db/`:

| Model | Tabela | Opis |
|-------|--------|------|
| **User** | `users` | Użytkownik — zwykły (`user`) lub administrator (`admin`). |
| **Task** | `tasks` | Zadanie; proste testy (porównanie outputu) albo sprawdzarka. |
| **Submission** | `submissions` | Zgłoszenie rozwiązania; kolejka → ocena w tle. |
| **TestResult** | `test_results` | Wynik pojedynczego testu dla zgłoszenia. |

## Wymagania

- Python 3.12+
- Docker (opcjonalnie)

## Lokalnie

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

uvicorn ksi.main:app --reload --app-dir src
```

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok"}
```

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
