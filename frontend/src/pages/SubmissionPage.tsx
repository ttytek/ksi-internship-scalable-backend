import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import type { SubmissionDetail } from "../types";
import { StatusBadge, formatDate, statusLabel } from "../status";

const PENDING = new Set(["queued", "running"]);

export default function SubmissionPage() {
  const { submissionId } = useParams<{ submissionId: string }>();
  const [sub, setSub] = useState<SubmissionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!submissionId) return;
    api
      .getSubmission(submissionId)
      .then(setSub)
      .catch((e: Error) => setError(e.message));
  }, [submissionId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!sub || !PENDING.has(sub.status)) return;
    const id = window.setInterval(load, 1000);
    return () => window.clearInterval(id);
  }, [sub, load]);

  if (error) return <p className="error">Błąd: {error}</p>;
  if (!sub) return <p className="muted">Ładowanie…</p>;

  return (
    <div>
      <div className="page-head">
        <h1>Zgłoszenie</h1>
        <p className="muted">
          {sub.task_title && (
            <>
              Zadanie: <Link to={`/tasks/${sub.task_id}`}>{sub.task_title}</Link>
              {" · "}
            </>
          )}
          {sub.username && <>@{sub.username} · </>}
          {formatDate(sub.created_at)}
        </p>
      </div>

      <section className="card">
        <div className="row gap">
          <StatusBadge status={sub.status} />
          <span>
            Wynik: {sub.score ?? "—"} / {sub.max_score ?? "—"}
          </span>
          <span className="muted">język: {sub.language}</span>
          {PENDING.has(sub.status) && <span className="muted">odświeżanie…</span>}
        </div>
        {sub.compile_message && (
          <div className="mt">
            <strong>Komunikat</strong>
            <pre className="code-block">{sub.compile_message}</pre>
          </div>
        )}
      </section>

      <section className="card">
        <h2>Kod</h2>
        <pre className="code-block">{sub.source_code}</pre>
      </section>

      <section className="card">
        <h2>Wyniki testów</h2>
        {sub.test_results.length === 0 ? (
          <p className="muted">
            {PENDING.has(sub.status)
              ? "Oczekiwanie na sędziego…"
              : "Brak wyników testów (np. błąd kompilacji)."}
          </p>
        ) : (
          <div className="results">
            {sub.test_results.map((tr) => (
              <div key={tr.id} className={`result ${tr.passed ? "ok" : "fail"}`}>
                <div className="result-head">
                  <strong>
                    Test #{tr.ordinal}{" "}
                    {tr.visibility === "hidden" ? "(ukryty)" : "(przykład)"}
                  </strong>
                  <StatusBadge status={tr.verdict} />
                  <span className="muted">
                    {tr.points_awarded} pkt
                    {tr.time_ms != null && ` · ${tr.time_ms} ms`}
                  </span>
                </div>
                {tr.message && <p className="muted">{tr.message}</p>}
                {tr.visibility === "public" && (
                  <div className="sample-pair">
                    {tr.input != null && (
                      <div>
                        <strong>Input</strong>
                        <pre className="code-block">{tr.input}</pre>
                      </div>
                    )}
                    {tr.expected_output != null && (
                      <div>
                        <strong>Oczekiwane</strong>
                        <pre className="code-block">{tr.expected_output}</pre>
                      </div>
                    )}
                    {tr.actual_output != null && (
                      <div>
                        <strong>Twoje wyjście</strong>
                        <pre className="code-block">{tr.actual_output}</pre>
                      </div>
                    )}
                  </div>
                )}
                {tr.visibility === "hidden" && !tr.passed && (
                  <p className="muted">
                    Ukryty test nie przeszedł: {statusLabel(tr.verdict)}.
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
