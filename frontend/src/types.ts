export type User = {
  id: string;
  username: string;
  created_at: string;
};

export type TaskSummary = {
  id: string;
  slug: string;
  title: string;
  difficulty: number | null;
  judge_mode: string;
  time_limit_ms: number;
  memory_limit_mb: number;
  created_at: string;
};

export type TaskTestPublic = {
  id: string;
  ordinal: number;
  visibility: string;
  input: string;
  expected_output: string;
  points: number;
};

export type TaskDetail = TaskSummary & {
  statement: string;
  public_tests: TaskTestPublic[];
};

export type SubmissionSummary = {
  id: string;
  task_id: string;
  user_id: string;
  language: string;
  status: string;
  score: number | null;
  max_score: number | null;
  created_at: string;
  judged_at: string | null;
  task_title: string | null;
  username: string | null;
};

export type TestResultOut = {
  id: string;
  test_id: string;
  ordinal: number;
  verdict: string;
  passed: boolean;
  points_awarded: number;
  message: string | null;
  time_ms: number | null;
  memory_kb: number | null;
  visibility: string | null;
  input: string | null;
  expected_output: string | null;
  actual_output: string | null;
};

export type SubmissionDetail = SubmissionSummary & {
  source_code: string;
  compile_message: string | null;
  test_results: TestResultOut[];
};

export type TaskRankEntry = {
  rank: number;
  user_id: string;
  username: string;
  submission_id: string;
  language: string;
  solved_at: string;
  score: number | null;
};

export type GlobalRankEntry = {
  rank: number;
  user_id: string;
  username: string;
  solved_count: number;
};
