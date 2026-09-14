/**
 * Low-level API client. Talks to the FastAPI backend in its own wire
 * format (snake_case, matching backend/app/schemas.py exactly) — the
 * `lib/tasks.ts` / `reviews.ts` / `employee-file.ts` files each map these
 * into the app's existing camelCase domain types, so the components never
 * see snake_case.
 *
 * Auth: the JWT lives in localStorage (this is a real browser app, not a
 * Claude artifact — that restriction doesn't apply here). Every request
 * attaches it as a Bearer token when present.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const TOKEN_KEY = "venv_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  window.localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (
    !(options.body instanceof URLSearchParams) &&
    !(options.body instanceof FormData) &&
    options.body
  ) {
    headers.set("Content-Type", "application/json");
  }
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  } catch {
    throw new ApiError(0, "Can't reach the server — is the backend running?");
  }

  if (!res.ok) {
    let detail = res.statusText || `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") detail = data.detail;
    } catch {
      // response wasn't JSON — keep the statusText fallback
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Same auth/error handling as request(), but for binary responses
 * (attachment downloads) — a plain <img src> or <a href> can't attach the
 * Bearer token, so callers fetch the blob here and hand it an object URL. */
async function requestBlob(path: string): Promise<Blob> {
  const headers = new Headers();
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { headers });
  } catch {
    throw new ApiError(0, "Can't reach the server — is the backend running?");
  }
  if (!res.ok) {
    throw new ApiError(res.status, res.statusText || `Request failed (${res.status})`);
  }
  return res.blob();
}

// ---- Wire types — mirror backend/app/schemas.py field-for-field ----

export type ApiAgentType =
  | "manager"
  | "mentor"
  | "hr"
  | "security_reviewer"
  | "data_reviewer"
  | "career_coach"
  | "devops";
export type ApiTaskStatus = "todo" | "in_progress" | "submitted" | "reviewed";
export type ApiSenderType = "user" | "agent";

export interface UserApiOut {
  id: string;
  email: string;
  full_name: string;
  track: string;
  is_active: boolean;
  created_at: string;
  has_cv: boolean;
}

export interface TaskMessageApiOut {
  id: string;
  sender_type: ApiSenderType;
  agent_type: ApiAgentType | null;
  content: string;
  created_at: string;
}

export interface TaskAttachmentApiOut {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  uploaded_at: string;
}

export interface TaskApiOut {
  id: string;
  title: string;
  description: string;
  status: ApiTaskStatus;
  github_link: string | null;
  submission_text: string | null;
  attachments: TaskAttachmentApiOut[];
  created_by_agent: ApiAgentType;
  // week_id/deadline are null for tasks outside the weekly-cycle flow.
  week_id: string | null;
  deadline: string | null;
  submitted_at: string | null;
  completed_at: string | null;
  // null until both deadline and completed_at exist.
  is_late: boolean | null;
  created_at: string;
  updated_at: string;
}

export interface TaskDetailApiOut extends TaskApiOut {
  messages: TaskMessageApiOut[];
}

export type ApiReviewKind = "task_review" | "week_progress" | "behavioral" | "skills_rollup";

export interface RubricCategoryApi {
  key: string;
  label: string;
  score: number;
}

export interface ReviewCommentApi {
  category: string;
  content: string;
}

export interface MentorMetricsApi {
  verdict: "approved" | "needs_changes";
  categories: RubricCategoryApi[];
  comments: ReviewCommentApi[];
}

export interface HrMetricsApi {
  reviewed_task_count: number;
  average_score: number | null;
}

export interface WeekProgressMetricsApi {
  subtasks_completed: number;
  subtasks_needed_changes: number;
}

export interface BehavioralMetricsApi {
  attended_days: number;
  absent_days: number;
  late_task_count: number;
  total_subtasks: number;
  consistency_rating: "strong" | "adequate" | "needs_improvement";
}

export interface ReviewApiOut {
  id: string;
  task_id: string | null;
  // null for task_review (tied to task_id instead) and skills_rollup
  // (periodic, tied to neither).
  week_id: string | null;
  agent_type: ApiAgentType;
  kind: ApiReviewKind;
  content: string;
  metrics_json:
    | MentorMetricsApi
    | HrMetricsApi
    | WeekProgressMetricsApi
    | BehavioralMetricsApi
    | null;
  created_at: string;
}

export interface EmployeeFileApiOut {
  skills_json: { items?: string[] };
  strengths_json: { items?: string[] };
  growth_areas_json: { items?: string[] };
  summary_text: string | null;
  updated_at: string;
}

export interface DashboardApiOut {
  tasks_completed: number;
  tasks_total: number;
  on_time_rate: number | null;
  average_score: number | null;
  reviews_count: number;
  weeks_completed: number;
  weeks_total: number;
  has_active_project: boolean;
}

export interface ChatMessageApiOut {
  id: string;
  agent_type: ApiAgentType;
  sender_type: "user" | "agent";
  content: string;
  created_at: string;
}

// ---- Project & Week (weekly-cycle flow) ----

export type ApiProjectStatus = "active" | "completed";
export type ApiWeekStatus = "active" | "completed";

export interface SubtaskPlanApi {
  title: string;
  description: string;
  deadline: string;
}

export interface WeekApiOut {
  id: string;
  project_id: string;
  week_number: number;
  status: ApiWeekStatus;
  big_task_title: string;
  big_task_description: string;
  next_subtask_index: number;
  subtasks_plan_json: SubtaskPlanApi[];
  started_at: string;
  target_end_at: string;
  ended_at: string | null;
}

export interface ProjectApiOut {
  id: string;
  title: string;
  description: string;
  status: ApiProjectStatus;
  created_at: string;
  updated_at: string;
  weeks: WeekApiOut[];
}

// ---- Stage 2 onboarding (docs/STAGE2_ONBOARDING_FLOW.md) ----

export type ApiTrack =
  | "junior_dev"
  | "software_engineering"
  | "data_science_ai"
  | "cybersecurity"
  | "networks_infrastructure"
  | "information_systems"
  | "cloud_devops";

export interface AgentCatalogApiOut {
  id: string;
  name: string;
  description: string;
}

export interface OnboardingQuestionsApiOut {
  questions: string[];
}

export interface OnboardingTrackApiOut {
  suggested_track: ApiTrack;
  reasoning: string;
}

export interface OnboardingAgentsApiOut {
  suggested_agents: AgentCatalogApiOut[];
}

export interface OnboardingCompleteApiOut {
  track: ApiTrack;
  agents: AgentCatalogApiOut[];
}

export type ApiOnboardingStage = "cv" | "qa" | "track" | "agents" | "complete";

export interface OnboardingStateApiOut {
  onboarding_stage: ApiOnboardingStage;
  track: ApiTrack;
  track_confirmed: boolean;
  suggested_track: ApiTrack | null;
}

export interface ProjectOwnApiOut {
  id: string;
  title: string;
  description: string;
  status: ApiProjectStatus;
  source: "manager" | "own";
  created_at: string;
  updated_at: string;
}

// ---- API surface ----

export const api = {
  auth: {
    register: (email: string, password: string, fullName: string) =>
      request<UserApiOut>("/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password, full_name: fullName }),
      }),
    login: (email: string, password: string) =>
      request<{ access_token: string; token_type: string }>("/auth/login", {
        method: "POST",
        body: new URLSearchParams({ username: email, password }),
      }),
  },

  me: () => request<UserApiOut>("/users/me"),

  cv: {
    submit: (cvRawText: string) =>
      request<UserApiOut>("/users/me/cv", {
        method: "POST",
        body: JSON.stringify({ cv_raw_text: cvRawText }),
      }),
  },

  onboarding: {
    /** Full optional-agent catalog, not just the ones suggested for the
     * graduate's track — the roster step needs the whole list so the
     * graduate can add ones the agent didn't suggest. No auth required. */
    catalog: () => request<AgentCatalogApiOut[]>("/onboarding/catalog"),
    /** The graduate's selected optional agents only — Manager/Mentor/HR
     * are always on the team and aren't in this list. Powers the board
     * graph and orientation screen. */
    myAgents: () => request<AgentCatalogApiOut[]>("/users/me/agents"),
    state: () => request<OnboardingStateApiOut>("/onboarding/state"),
    uploadCv: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return request<OnboardingQuestionsApiOut>("/onboarding/cv", {
        method: "POST",
        body: form,
      });
    },
    submitQa: (answers: Record<string, string>, introText: string) =>
      request<OnboardingTrackApiOut>("/onboarding/qa", {
        method: "POST",
        body: JSON.stringify({ answers, intro_text: introText || null }),
      }),
    /** track: null approves the suggestion as-is; pass a track to override it. */
    approveTrack: (track: ApiTrack | null) =>
      request<OnboardingAgentsApiOut>("/onboarding/track", {
        method: "POST",
        body: JSON.stringify({ track }),
      }),
    approveAgents: (agentIds: string[]) =>
      request<OnboardingCompleteApiOut>("/onboarding/agents", {
        method: "POST",
        body: JSON.stringify({ agent_ids: agentIds }),
      }),
  },

  tasks: {
    list: () => request<TaskApiOut[]>("/tasks"),
    detail: (id: string) => request<TaskDetailApiOut>(`/tasks/${id}`),
    updateStatus: (id: string, status: ApiTaskStatus, githubLink?: string) =>
      request<TaskApiOut>(`/tasks/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status, github_link: githubLink ?? null }),
      }),
    /** Stage 2: a submission is a GitHub link, free text, and/or file/
     * image attachments — at least one, not github_link specifically. */
    submit: (
      id: string,
      payload: { githubLink?: string; submissionText?: string; files?: File[] }
    ) => {
      const form = new FormData();
      if (payload.githubLink) form.append("github_link", payload.githubLink);
      if (payload.submissionText) form.append("submission_text", payload.submissionText);
      for (const file of payload.files ?? []) form.append("files", file);
      return request<TaskApiOut>(`/tasks/${id}/submit`, { method: "POST", body: form });
    },
    attachmentBlob: (taskId: string, attachmentId: string) =>
      requestBlob(`/tasks/${taskId}/attachments/${attachmentId}`),
    postMessage: (id: string, content: string) =>
      request<TaskMessageApiOut>(`/tasks/${id}/messages`, {
        method: "POST",
        body: JSON.stringify({ content }),
      }),
    review: (id: string) => request<ReviewApiOut>(`/tasks/${id}/review`),
  },

  agents: {
    assignTask: () =>
      request<TaskApiOut>("/agents/manager/assign-task", { method: "POST" }),
    managerReply: (taskId: string) =>
      request<TaskMessageApiOut>(`/agents/manager/reply/${taskId}`, {
        method: "POST",
      }),
    mentorReview: (taskId: string) =>
      request<ReviewApiOut>(`/agents/mentor/review/${taskId}`, {
        method: "POST",
      }),
    hrRollup: () =>
      request<ReviewApiOut>("/agents/hr/rollup", { method: "POST" }),
  },

  employeeFile: () => request<EmployeeFileApiOut>("/users/me/employee-file"),
  reviews: () => request<ReviewApiOut[]>("/users/me/reviews"),
  dashboard: () => request<DashboardApiOut>("/users/me/dashboard"),

  projects: {
    /** The graduate's active Project + all its Weeks. 404s until they've
     * gotten their first task — see lib/projects.ts's fetchMyProject,
     * which treats that as "nothing yet", not an error. */
    me: () => request<ProjectApiOut>("/projects/me"),
    /** Stage 2: bring your own project instead of the Manager improvising
     * one. Only works before the first assign-task call — 400s if the
     * graduate already has an active project. */
    createOwn: (title: string, description: string) =>
      request<ProjectOwnApiOut>("/projects/own", {
        method: "POST",
        body: JSON.stringify({ title, description }),
      }),
  },

  meeting: {
    history: (agent: string) =>
      request<ChatMessageApiOut[]>(`/meeting/${agent}`),
    send: (agent: string, content: string) =>
      request<ChatMessageApiOut>(`/meeting/${agent}`, {
        method: "POST",
        body: JSON.stringify({ content }),
      }),
  },
};
