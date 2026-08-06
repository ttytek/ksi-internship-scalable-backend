import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import type { SubmissionSummary } from "../types";
import { StatusBadge, formatDate } from "../status";

export default function SubmissionsPage() {
  const { user } = useAuth();
  const [rows, setRows] = useState<SubmissionSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    api
      .listUserSubmissions(user.id)
      .then(setRows)
      .catch((e: Error) => setError(e.message));
  }, [user]);

  if (error) return <p className="error">Błąd: {error}</p>;
  if (!rows) return <p className="muted">Ładowanie…</p>;

  return (
    <div>
      <div className="page-head">
        <h1>Moje zgłoszenia</h1>
        <p className="muted">Historia wysłanych rozwiązań.</p>
      </div>
      {rows.length === 0 ? (
        <p className="muted">Brak zgłoszeń. Wybierz zadanie i wyślij kod.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Zadanie</th>
                <th>Status</th>
                <th>Wynik</th>
                <th>Kiedy</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((s) => (
                <tr key={s.id}>
                  <td>
                    <Link to={`/submissions/${s.id}`}>
                      {s.task_title ?? s.task_id.slice(0, 8)}
                    </Link>
                  </td>
                  <td>
                    <StatusBadge status={s.status} />
                  </td>
                  <td>
                    {s.score ?? "—"} / {s.max_score ?? "—"}
                  </td>
                  <td className="muted">{formatDate(s.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
