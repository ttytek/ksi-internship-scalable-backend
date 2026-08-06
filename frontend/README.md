# KSI Frontend

Prosty frontend (React + Vite) do przeglądania zadań, wysyłania rozwiązań i rankingu.

## Uruchomienie

Wymaga działającego API na `http://127.0.0.1:8000` (proxy `/api` → backend).

```bash
npm install
npm run dev
```

Aplikacja: http://127.0.0.1:5173

## Funkcje

- logowanie po username (bez hasła)
- lista zadań i treść z przykładami
- wysyłka kodu Python
- podgląd zgłoszenia (werdykty testów public/hidden)
- ranking globalny i ranking przy zadaniu
