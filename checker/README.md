# KSI checker

Worker sędziego. Osobny proces / kontener, skalowany poziomo (`docker compose up --scale checker=N`).

Zależy od pakietu `ksi` (modele, S3, sesja DB). **Nie** odpala migracji.

## Protokół

1. Idle: `XREADGROUP` ze streamu `ksi.submissions` (payload: `submission_id`).
2. Claim w Postgresie: `UPDATE … WHERE id=? AND status='queued'` + `judge_claim_id`.
3. Sędziowanie **bez** trzymania połączenia DB na czas `subprocess`.
4. Heartbeat lease; zapis wyników tylko gdy `judge_claim_id` się zgadza.
5. **Sticky drain:** po zadaniu *P* kolejny claim to `WHERE task_id=P AND status='queued'`, bez czytania streamu, aż kolejka *P* jest pusta.
6. Sweeper (w tej samej pętli): wygasłe `running` → z powrotem `queued` albo `internal_error` po `CHECKER_MAX_ATTEMPTS` (domyślnie 3).

Redis jest obudzeniem. Źródło prawdy to wiersz w `submissions`.

## Uruchomienie

API musi raz wystartować (tworzy rolę `ksi_checker`). Potem:

```bash
pip install -e ".[dev]"
export DATABASE_URL=postgresql+psycopg://ksi_checker:ksi_checker@localhost:5432/ksi
export REDIS_URL=redis://localhost:6379/0
python -m ksi_checker
```

Albo z katalogu głównego:

```bash
docker compose up --build --scale checker=3
```

## Testy

```bash
pip install -e ".[dev]"
pytest -q
```

`pythonpath` obejmuje `../backend/src`.
