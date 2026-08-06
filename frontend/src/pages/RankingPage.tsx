import { useEffect, useState } from "react";
import { api } from "../api";
import type { GlobalRankEntry } from "../types";

export default function RankingPage() {
  const [rows, setRows] = useState<GlobalRankEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .globalRanking()
      .then(setRows)
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <p className="error">Błąd: {error}</p>;
  if (!rows) return <p className="muted">Ładowanie…</p>;

  return (
    <div>
      <div className="page-head">
        <h1>Ranking globalny</h1>
        <p className="muted">Liczba unikalnych zadań rozwiązanych (status accepted).</p>
      </div>
      {rows.length === 0 ? (
        <p className="muted">Jeszcze nikt nic nie rozwiązał.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Użytkownik</th>
                <th>Rozwiązane</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.user_id}>
                  <td>{r.rank}</td>
                  <td>{r.username}</td>
                  <td>{r.solved_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
