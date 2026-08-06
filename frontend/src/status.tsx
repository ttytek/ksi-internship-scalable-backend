const LABELS: Record<string, string> = {
  queued: "W kolejce",
  running: "Sprawdzanie…",
  accepted: "Accepted",
  wrong_answer: "Wrong Answer",
  time_limit: "Time Limit",
  runtime_error: "Runtime Error",
  compilation_error: "Compilation Error",
  internal_error: "Internal Error",
  memory_limit: "Memory Limit",
  passed: "OK",
};

export function statusLabel(status: string): string {
  return LABELS[status] ?? status;
}

export function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "accepted" || status === "passed"
      ? "badge ok"
      : status === "queued" || status === "running"
        ? "badge pending"
        : "badge fail";
  return <span className={cls}>{statusLabel(status)}</span>;
}

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("pl-PL");
  } catch {
    return iso;
  }
}
