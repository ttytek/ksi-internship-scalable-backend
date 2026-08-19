# KSI — prosta platforma zadań programistycznych

MVP w stylu LeetCode: użytkownicy przeglądają zadania, wysyłają rozwiązania w Pythonie, system je sprawdza i buduje ranking.

## Struktura

| Katalog / serwis | Opis |
|------------------|------|
| `frontend/` | React (Vite). Tylko rozmawia z API. `npm run dev`. |
| `backend/` | FastAPI: użytkownicy, zadania, zgłoszenia, ranking. **Właściciel Postgresa** (schemat, migracje). Nie uruchamia kodu użytkownika. |
| `checker/` | Worker sędziego. Redis Streams + claim w Postgresie. Skalowanie: `docker compose up --scale checker=N`. |
| `dataset/` | Przykładowe zadania (JSON) |

Infra: **Postgres**, **Redis**, **S3** (packi ukrytych testów).

```
browser → API: INSERT queued → 201
                └ XADD submission_id (gdy Redis leży: i tak 201)

checker: sticky drain zadania P z DB, inaczej XREADGROUP
         → claim w Postgresie → subprocess → zapis wyników
```

---

## Uruchomienie od zera (zalecane)

Wszystkie komendy poniżej zakładają katalog główny repozytorium.

### Wymagania

- Python **3.12+**
- Node.js **18+**
- Docker + Docker Compose

### Krok 1 — Postgres, Redis, API, checker

```bash
cd backend
cp .env.example .env   # uzupełnij S3_* jeśli seedujesz packi
cd ..

docker compose up --build
# poziomo: docker compose up --build --scale checker=3
```

- API: http://127.0.0.1:8000 (`/health`, `/docs`) — w compose zawsze port 8000
- Postgres: `localhost:5432` (user/hasło/baza: `ksi`)
- Redis: `localhost:6379`

`S3_*` biorą się z `backend/.env` (`env_file`). Compose **nie** interpoluje tego pliku: puste `${S3_*}` w `environment:` by je nadpisało, więc tam zostają tylko URL-e serwisów (`DATABASE_URL`, `REDIS_URL`). `APP_PORT` w `backend/.env` dotyczy lokalnego `uvicorn`, nie mapowania Dockera.

Wolumen bazy to `ksi_pgdata` (nie `backend_pgdata`). Gdy hostowy Postgres zajmuje 5432, zmień w `docker-compose.yml` mapowanie na `"5433:5432"` i `DATABASE_URL` na porcie 5433.

`cd backend && docker compose up` nadal działa (wrapper `include` + `make up`).

API przy starcie tworzy schemat i rolę `ksi_checker` (ograniczone GRANT-y). Checkery ładują się po zdrowym API.

### Krok 2 — Seed zadań (osobny terminal)

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m ksi.scripts.seed_dataset --dir ../dataset/problems
```

### Krok 3 — Frontend (osobny terminal)

```bash
cd frontend
npm install
npm run dev
```

UI: http://127.0.0.1:5173  
Frontend proxy’uje `/api` → backend (zob. `frontend/vite.config.ts`).

### Lokalnie bez Dockera (API + checker)

Postgres i Redis i tak w compose:

```bash
docker compose up -d db redis

# terminal 1 — API (superuser DB)
cd backend
source .venv/bin/activate
export DATABASE_URL=postgresql+psycopg://ksi:ksi@localhost:5432/ksi
export REDIS_URL=redis://localhost:6379/0
uvicorn ksi.main:app --reload --app-dir src --host 0.0.0.0 --port 8000

# terminal 2 — checker (po pierwszym starcie API, które zakłada rolę)
cd checker
pip install -e ".[dev]"
export DATABASE_URL=postgresql+psycopg://ksi_checker:ksi_checker@localhost:5432/ksi
export REDIS_URL=redis://localhost:6379/0
python -m ksi_checker
```

Jeśli rola jeszcze nie istnieje, odpal API raz albo użyj superusera tylko do debugowania.

---

## Co jest w MVP

- użytkownik bez ról i bez hasła (login = username)
- zadania z testami publicznymi (w DB) i ukrytymi (zip w S3)
- zgłoszenia: API kolejkuje, **checker** sędziuje Pythona (stdout)
- worker trzyma pack na dysku i **trzyma się tego zadania**, dopóki są `queued` zgłoszenia do niego
- wyniki testów (WA / TLE / RE / …)
- ranking per zadanie i globalny

## Świadomie poza MVP

- pełna autentykacja (hasła, JWT)
- sandbox bezpieczeństwa (kod użytkownika to `subprocess` w kontenerze checkera)
- języki inne niż Python
- tryb `checker` (jest w modelu, niezaimplementowany w sędzim)
