import type {
  GlobalRankEntry,
  SubmissionDetail,
  SubmissionSummary,
  TaskDetail,
  TaskRankEntry,
  TaskSummary,
  User,
} from "./types";

const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

export const api = {
  login: (username: string) =>
    request<User>("/users/login", {
      method: "POST",
      body: JSON.stringify({ username }),
    }),

  listTasks: () => request<TaskSummary[]>("/tasks"),

  getTask: (id: string) => request<TaskDetail>(`/tasks/${id}`),

  submit: (taskId: string, userId: string, sourceCode: string, language = "python") =>
    request<SubmissionSummary>(`/tasks/${taskId}/submissions`, {
      method: "POST",
      body: JSON.stringify({
        user_id: userId,
        source_code: sourceCode,
        language,
      }),
    }),

  getSubmission: (id: string) => request<SubmissionDetail>(`/submissions/${id}`),

  listUserSubmissions: (userId: string) =>
    request<SubmissionSummary[]>(`/users/${userId}/submissions`),

  taskRanking: (taskId: string) => request<TaskRankEntry[]>(`/tasks/${taskId}/ranking`),

  globalRanking: () => request<GlobalRankEntry[]>("/ranking"),
};
