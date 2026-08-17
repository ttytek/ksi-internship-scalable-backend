# KSI — prosta platforma zadań programistycznych

MVP w stylu LeetCode: użytkownicy przeglądają zadania, wysyłają rozwiązania w Pythonie, system je sprawdza i buduje ranking.

## Struktura

| Katalog | Opis |
|---------|------|
| `backend/` | FastAPI + SQLAlchemy + **Postgres** |
| `frontend/` | React (Vite) |
| `dataset/` | Przykładowe zadania (JSON) |

## Elementy systemu

1. **Postgres** — baza danych  
2. **API** (FastAPI, port domyślnie `8000` lub z `.env`) — logika, sędzia  
3. **Seed** — jednorazowy import zadań z `dataset/problems`  
4. **Frontend** (Vite, port `5173`) — UI  

---

## Uruchomienie od zera (zalecane)

Wszystkie komendy poniżej zakładają katalog główny repozytorium:

```bash
cd /ścieżka/do/ksi
```

### Wymagania

- Python **3.12+**
- Node.js **18+** (u Ciebie jest 21 — OK)
- Docker + Docker Compose
- Użytkownik w grupie `docker` (albo używasz `sudo docker …`)

```bash
# raz: grupa docker (potem wyloguj i zaloguj się ponownie)
sudo usermod -aG docker $USER

# Docker musi być włączony
sudo systemctl start docker
sudo systemctl enable docker   # opcjonalnie: start przy bootowaniu
```

### Krok 1 — Postgres (Docker)

```bash
cd backend

# jeśli plik .env nie istnieje:
cp .env.example .env
# w .env możesz ustawić np. APP_PORT=8000
```

**Uwaga o porcie 5432:** jeśli na hoście już działa systemowy Postgres, kontener nie wystartuje albo seed dostanie błąd hasła (`user "ksi"`). Wtedy:

- w `docker-compose.yml` zmień mapowanie na `"5433:5432"` (albo inny wolny port), **oraz**
- ustaw w środowisku / `.env`:

```bash
DATABASE_URL=postgresql+psycopg://ksi:ksi@localhost:5433/ksi
```

Start bazy:

```bash
docker compose up -d db
docker compose ps          # db = healthy
```

Sprawdzenie połączenia:

```bash
# hasło: ksi
psql "postgresql://ksi:ksi@localhost:5432/ksi" -c 'SELECT 1'
# jeśli mapowałeś na 5433 — zamień port w URL
```

### Krok 2 — Backend (API)

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# domyślnie: postgresql+psycopg://ksi:ksi@localhost:5432/ksi
# nadpisz tylko jeśli zmieniasz port / hasło:
# export DATABASE_URL=postgresql+psycopg://ksi:ksi@localhost:5433/ksi

uvicorn ksi.main:app --reload --app-dir src --host 0.0.0.0 --port 8000
```

Jeśli w `backend/.env` masz `APP_PORT=8888`, użyj tego portu konsekwentnie:

```bash
uvicorn ksi.main:app --reload --app-dir src --host 0.0.0.0 --port 8888
```

Sprawdzenie:

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok"}
```

Dokumentacja API: http://127.0.0.1:8000/docs  

*(zostaw ten terminal włączony)*

### Krok 3 — Seed zadań (osobny terminal)

Zadania z testami prywatnymi/generowanymi idą do S3 (zip per rewizja). Uzupełnij w `backend/.env` zmienne `S3_*` z `.env.example`.

Bez bucketa / kluczy seed **nie** zaimportuje `brcktsrm` itd. — oczekiwany wynik to
`ERR  …: S3 is not configured but this problem has private/generated tests`.
Same przykłady publiczne seedują się bez S3.

```bash
cd backend
source .venv/bin/activate
# ten sam DATABASE_URL co API
python -m ksi.scripts.seed_dataset --dir ../dataset/problems
```

Z działającym S3: linie `ok   brcktsrm …`, `ok   comm3 …` itd.

Doklejenie nowej rewizji packa: `python -m ksi.scripts.attach_main_pack --slug … --zip pack.zip`.

### Krok 4 — Frontend (osobny terminal)

```bash
cd frontend
npm install
npm run dev
```

UI: http://127.0.0.1:5173  

Frontend proxy’uje `/api` → `http://127.0.0.1:8000`.  
Jeśli API działa na **innym porcie** (np. `8888`), zmień `frontend/vite.config.ts` (`server.proxy["/api"].target`).

### Krok 5 — Użycie

1. Otwórz http://127.0.0.1:5173  
2. **Zaloguj** — wpisz username (bez hasła; konto powstanie automatycznie)  
3. Lista **Zadań** → treść → wklej kod Python → **Wyślij**  
4. Zobacz wynik testów / ranking  

---

## Alternatywa: API też w Dockerze

```bash
cd backend
# ustaw APP_PORT w .env (np. 8000)
docker compose up --build
```

To odpala **db + api**. Seed nadal odpalasz lokalnie (z venv) wskazując na hostowy port Postgresa:

```bash
export DATABASE_URL=postgresql+psycopg://ksi:ksi@localhost:5432/ksi
python -m ksi.scripts.seed_dataset --dir ../dataset/problems
```

---

## Typowe problemy

| Objaw | Przyczyna | Co zrobić |
|-------|-----------|-----------|
| `password authentication failed for user "ksi"` | Na porcie siedzi **inny** Postgres (systemowy), nie kontener `ksi` | Zmień port mapowania Dockera albo zatrzymaj systemowy Postgres |
| `connection refused` / brak Dockera | Daemon wyłączony | `sudo systemctl start docker` |
| `permission denied` na `docker.sock` | Brak grupy `docker` | `sudo usermod -aG docker $USER` + ponowne logowanie; tymczasowo `sudo docker compose …` |
| Frontend nie widzi API | Zły port proxy | Dopasuj `vite.config.ts` do portu API |
| Pusta lista zadań | Brak seeda albo seed bez S3 | Krok 3 — uzupełnij `S3_*` albo zaakceptuj `ERR … S3 is not configured` |
| `ERR … S3 is not configured` przy seedzie | Puste `S3_BUCKET` / klucze; dataset ma generated tests | Uzupełnij `S3_*` w `.env` (bez MinIO w compose) |

---

## Co jest w MVP

- użytkownik bez ról i bez hasła (login = username)
- zadania z testami publicznymi (w DB) i ukrytymi (zip w S3, rewizje)
- zgłoszenia + sędzia Python (porównanie stdout)
- wyniki testów (WA / TLE / RE / …)
- ranking per zadanie i globalny

## Świadomie poza MVP

- pełna autentykacja (hasła, JWT)
- sandbox bezpieczeństwa
- języki inne niż Python
- tryb `checker` (jest w modelu, niezaimplementowany w sędzim)
