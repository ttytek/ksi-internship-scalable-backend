import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { TaskSummary } from "../types";

export default function TasksPage() {
  const [tasks, setTasks] = useState<TaskSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listTasks()
      .then(setTasks)
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <p className="error">Błąd: {error}</p>;
  if (!tasks) return <p className="muted">Ładowanie zadań…</p>;

  return (
    <div>
      <div className="page-head">
        <h1>Zadania</h1>
        <p className="muted">Wybierz zadanie, przeczytaj treść i wyślij rozwiązanie w Pythonie.</p>
      </div>
      {tasks.length === 0 ? (
        <div className="card">
          <p>
            Brak zadań w bazie. Uruchom seed z backendu:
          </p>
          <pre className="code-block">
            {`cd backend
python -m ksi.scripts.seed_dataset --dir ../dataset/problems`}
          </pre>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Tytuł</th>
                <th>Slug</th>
                <th>Trudność</th>
                <th>Limit czasu</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((t) => (
                <tr key={t.id}>
                  <td>
                    <Link to={`/tasks/${t.id}`}>{t.title}</Link>
                  </td>
                  <td>
                    <code>{t.slug}</code>
                  </td>
                  <td>{t.difficulty ?? "—"}</td>
                  <td>{t.time_limit_ms} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
