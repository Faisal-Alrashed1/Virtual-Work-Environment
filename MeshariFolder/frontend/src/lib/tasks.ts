import { api, type ApiTaskStatus, type TaskApiOut, type TaskDetailApiOut } from "./api";
import type { AgentId } from "./agents";

export type TaskStatus = ApiTaskStatus;
export type SenderType = "user" | "agent";

export interface TaskMessage {
  id: string;
  senderType: SenderType;
  // The Manager posts thread replies; Stage 2's co-reviewers (Security
  // Reviewer/Data Reviewer/DevOps) post here too after the Mentor's
  // review, if they're on the graduate's roster — so this is any agent
  // id, not just the fixed default three. See lib/agent-display.ts.
  agentType: string | null;
  content: string;
  createdAt: string;
}

export interface TaskAttachment {
  id: string;
  filename: string;
  contentType: string;
  sizeBytes: number;
  uploadedAt: string;
}

export interface Task {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  githubLink: string | null;
  submissionText: string | null;
  attachments: TaskAttachment[];
  createdByAgent: AgentId;
  // null for tasks outside the weekly-cycle flow (e.g. any manually
  // created via the admin POST /tasks, which the app itself never calls).
  weekId: string | null;
  deadline: string | null;
  submittedAt: string | null;
  completedAt: string | null;
  // null until both deadline and completedAt exist.
  isLate: boolean | null;
  createdAt: string;
  updatedAt: string;
  messages: TaskMessage[];
}

export const STATUS_ORDER: TaskStatus[] = [
  "todo",
  "in_progress",
  "submitted",
  "reviewed",
];

export const STATUS_LABEL: Record<TaskStatus, string> = {
  todo: "To do",
  in_progress: "In progress",
  submitted: "Submitted",
  reviewed: "Reviewed",
};

function toTaskMessage(m: TaskDetailApiOut["messages"][number]): TaskMessage {
  return {
    id: m.id,
    senderType: m.sender_type,
    agentType: m.agent_type,
    content: m.content,
    createdAt: m.created_at,
  };
}

function toTask(t: TaskApiOut, messages: TaskMessage[] = []): Task {
  return {
    id: t.id,
    title: t.title,
    description: t.description,
    status: t.status,
    githubLink: t.github_link,
    submissionText: t.submission_text,
    attachments: t.attachments.map((a) => ({
      id: a.id,
      filename: a.filename,
      contentType: a.content_type,
      sizeBytes: a.size_bytes,
      uploadedAt: a.uploaded_at,
    })),
    // Only the Manager assigns tasks today — same reasoning as
    // toTaskMessage's cast above.
    createdByAgent: t.created_by_agent as AgentId,
    weekId: t.week_id,
    deadline: t.deadline,
    submittedAt: t.submitted_at,
    completedAt: t.completed_at,
    isLate: t.is_late,
    createdAt: t.created_at,
    updatedAt: t.updated_at,
    messages,
  };
}

/** List view — lightweight, no thread (matches GET /tasks). */
export async function fetchTasks(): Promise<Task[]> {
  const raw = await api.tasks.list();
  return raw.map((t) => toTask(t));
}

/** Full detail with thread (matches GET /tasks/{id}) — call when a task is opened. */
export async function fetchTaskDetail(id: string): Promise<Task> {
  const raw = await api.tasks.detail(id);
  return toTask(raw, raw.messages.map(toTaskMessage));
}

export async function startTask(id: string): Promise<Task> {
  const raw = await api.tasks.updateStatus(id, "in_progress");
  return toTask(raw);
}

/** Stage 2: a submission is a GitHub link, free text, and/or file/image
 * attachments — at least one, not github_link specifically. The older
 * PATCH-based path (github_link only) still exists on the backend for
 * anything else calling it, but the app itself always submits this way now. */
export async function submitTask(
  id: string,
  payload: { githubLink?: string; submissionText?: string; files?: File[] }
): Promise<Task> {
  const raw = await api.tasks.submit(id, payload);
  return toTask(raw);
}

export async function postUserMessage(id: string, content: string): Promise<TaskMessage> {
  const raw = await api.tasks.postMessage(id, content);
  return toTaskMessage(raw);
}

/** Manager assigns the next task — first one, or another once ready for more. */
export async function assignNextTask(): Promise<Task> {
  const raw = await api.agents.assignTask();
  return toTask(raw);
}

/** Manager replies in a task's thread after the graduate posts a message. */
export async function managerReply(taskId: string): Promise<TaskMessage> {
  const raw = await api.agents.managerReply(taskId);
  return toTaskMessage(raw);
}

/** Mentor reviews a submitted task and moves it to 'reviewed'. */
export async function requestMentorReview(taskId: string): Promise<Task> {
  await api.agents.mentorReview(taskId);
  return fetchTaskDetail(taskId);
}
