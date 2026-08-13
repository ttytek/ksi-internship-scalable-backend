import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import type { SubmissionDetail } from "../types";
import { StatusBadge, formatDate } from "../status";

const PENDING = new Set(["queued", "running"]);

export default function SubmissionPage() {
  const { submissionId } = useParams<{ submissionId: string }>();
  const [sub, setSub] = useState<SubmissionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

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

  async function copyCode() {
    if (!sub) return;
    try {
      await navigator.clipboard.writeText(sub.source_code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("Nie udało się skopiować kodu do schowka.");
    }
  }

  function downloadCode() {
    if (!sub) return;
    const ext =
      sub.language === "python" || sub.language === "py"
        ? "py"
        : sub.language.replace(/[^a-z0-9]/gi, "") || "txt";
    const slug =
      (sub.task_title ?? "solution")
        .toLowerCase()
        .replace(/[^a-z0-9]+/gi, "-")
        .replace(/^-|-$/g, "") || "solution";
    const shortId = sub.id.slice(0, 8);
    const filename = `${slug}-${shortId}.${ext}`;

    const blob = new Blob([sub.source_code], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  if (error && !sub) return <p className="error">Błąd: {error}</p>;
  if (!sub) return <p className="muted">Ładowanie…</p>;

  // Only public sample tests are shown — no details about hidden cases.
  const publicResults = sub.test_results.filter((tr) => tr.visibility === "public");
  const hiddenCount = sub.test_results.length - publicResults.length;

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
        <div className="row gap section-head">
          <h2>Kod</h2>
          <div className="row gap">
            <button type="button" className="btn ghost" onClick={copyCode}>
              {copied ? "Skopiowano" : "Skopiuj kod"}
            </button>
            <button type="button" className="btn ghost" onClick={downloadCode}>
              Pobierz plik
            </button>
          </div>
        </div>
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
        ) : publicResults.length === 0 ? (
          <p className="muted">
            {hiddenCount > 0
              ? "Szczegóły testów nie są publiczne. Patrz status i wynik powyżej."
              : "Brak publicznych wyników testów."}
          </p>
        ) : (
          <div className="results">
            {publicResults.map((tr) => (
              <div key={tr.id} className={`result ${tr.passed ? "ok" : "fail"}`}>
                <div className="result-head">
                  <strong>Przykład #{tr.ordinal}</strong>
                  <StatusBadge status={tr.verdict} />
                  <span className="muted">
                    {tr.points_awarded} pkt
                    {tr.time_ms != null && ` · ${tr.time_ms} ms`}
                  </span>
                </div>
                {tr.message && <p className="muted">{tr.message}</p>}
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
              </div>
            ))}
            {hiddenCount > 0 && (
              <p className="muted">
                Szczegóły ukrytych testów nie są wyświetlane.
              </p>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
