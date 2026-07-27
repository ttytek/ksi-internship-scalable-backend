# KSI

Backend API (FastAPI).

## Encje domenowe

Opis pojęć systemu (kod: `src/ksi/domain/`):

| Encja | Opis |
|-------|------|
| **User** | Użytkownik — zwykły (`user`) lub administrator (`admin`). |
| **Task** | Zadanie programistyczne; oceniane prostymi testami (porównanie outputu) albo sprawdzarką. |
| **Submission** | Zgłoszenie rozwiązania; trafia do kolejki i jest oceniane w tle. |
| **TestResult** | Wynik pojedynczego testu dla danego zgłoszenia. |

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
