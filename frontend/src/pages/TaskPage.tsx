import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import type { TaskDetail, TaskRankEntry } from "../types";
import { formatDate } from "../status";

const DEFAULT_CODE = `import sys

def main():
    data = sys.stdin.read()
    # TODO: rozwiąż zadanie
    print(data, end="")

if __name__ == "__main__":
    main()
`;

export default function TaskPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const { user } = useAuth();
  const navigate = useNavigate();

  const [task, setTask] = useState<TaskDetail | null>(null);
  const [ranking, setRanking] = useState<TaskRankEntry[]>([]);
  const [code, setCode] = useState(DEFAULT_CODE);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!taskId) return;
    setError(null);
    Promise.all([api.getTask(taskId), api.taskRanking(taskId)])
      .then(([t, r]) => {
        setTask(t);
        setRanking(r);
      })
      .catch((e: Error) => setError(e.message));
  }, [taskId]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!user || !taskId) {
      navigate("/login");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const sub = await api.submit(taskId, user.id, code, "python");
      navigate(`/submissions/${sub.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Błąd wysyłki");
    } finally {
      setSubmitting(false);
    }
  }

  if (error && !task) return <p className="error">Błąd: {error}</p>;
  if (!task) return <p className="muted">Ładowanie…</p>;

  return (
    <div className="task-grid">
      <div>
        <div className="page-head">
          <h1>{task.title}</h1>
          <p className="muted">
            <code>{task.slug}</code> · limit {task.time_limit_ms} ms · {task.memory_limit_mb} MB
            {task.difficulty != null && <> · trudność {task.difficulty}</>}
          </p>
        </div>

        <section className="card">
          <h2>Treść</h2>
          <pre className="statement">{task.statement}</pre>
        </section>

        {task.public_tests.length > 0 && (
          <section className="card">
            <h2>Przykładowe testy</h2>
            {task.public_tests.map((t) => (
              <div key={t.id} className="sample">
                <h3>Przykład {t.ordinal}</h3>
                <div className="sample-pair">
                  <div>
                    <strong>Input</strong>
                    <pre className="code-block">{t.input}</pre>
                  </div>
                  <div>
                    <strong>Output</strong>
                    <pre className="code-block">{t.expected_output}</pre>
                  </div>
                </div>
              </div>
            ))}
          </section>
        )}

        <section className="card">
          <h2>Wyślij rozwiązanie (Python)</h2>
          {!user && (
            <p className="muted">
              Musisz się <Link to="/login">zalogować</Link>, żeby wysłać kod.
            </p>
          )}
          <form onSubmit={onSubmit}>
            <textarea
              className="code-input"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              rows={16}
              spellCheck={false}
            />
            {error && <p className="error">{error}</p>}
            <button className="btn primary" type="submit" disabled={!user || submitting}>
              {submitting ? "Wysyłanie…" : "Wyślij"}
            </button>
          </form>
        </section>
      </div>

      <aside>
        <section className="card sticky">
          <h2>Ranking zadania</h2>
          {ranking.length === 0 ? (
            <p className="muted">Nikt jeszcze nie rozwiązał.</p>
          ) : (
            <table className="compact">
              <thead>
                <tr>
                  <th>#</th>
                  <th>User</th>
                  <th>Kiedy</th>
                </tr>
              </thead>
              <tbody>
                {ranking.map((row) => (
                  <tr key={row.submission_id}>
                    <td>{row.rank}</td>
                    <td>{row.username}</td>
                    <td className="muted">{formatDate(row.solved_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </aside>
    </div>
  );
}
