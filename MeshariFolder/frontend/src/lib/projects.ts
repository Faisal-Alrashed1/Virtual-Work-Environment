import { api, type ProjectApiOut, type WeekApiOut } from "./api";

export type ProjectStatus = "active" | "completed";
export type WeekStatus = "active" | "completed";

export interface SubtaskPlan {
  title: string;
  description: string;
  deadline: string;
}

export interface Week {
  id: string;
  projectId: string;
  weekNumber: number;
  status: WeekStatus;
  bigTaskTitle: string;
  bigTaskDescription: string;
  /** How many of subtasksPlan have been handed out so far — a released
   * subtask counts here even before it's approved, so this is "handed
   * out" not "approved". Matches Week.next_subtask_index in models.py. */
  subtasksReleased: number;
  subtasksPlan: SubtaskPlan[];
  startedAt: string;
  targetEndAt: string;
  endedAt: string | null;
}

export interface Project {
  id: string;
  title: string;
  description: string;
  status: ProjectStatus;
  /** Real material (pasted notes and/or files) was given for an own project —
   * never the text itself. Always false for a Manager-authored project. */
  hasMaterials: boolean;
  weeks: Week[];
}

function toWeek(w: WeekApiOut): Week {
  return {
    id: w.id,
    projectId: w.project_id,
    weekNumber: w.week_number,
    status: w.status,
    bigTaskTitle: w.big_task_title,
    bigTaskDescription: w.big_task_description,
    subtasksReleased: w.next_subtask_index,
    subtasksPlan: w.subtasks_plan_json,
    startedAt: w.started_at,
    targetEndAt: w.target_end_at,
    endedAt: w.ended_at,
  };
}

function toProject(p: ProjectApiOut): Project {
  return {
    id: p.id,
    title: p.title,
    description: p.description,
    status: p.status,
    hasMaterials: p.has_materials,
    weeks: p.weeks.map(toWeek),
  };
}

/** The graduate's active Project with all its Weeks. null before they've
 * gotten their first task from the Manager — a normal state, not an
 * error, same as fetchTaskReview treating a missing review as null. */
export async function fetchMyProject(): Promise<Project | null> {
  try {
    const raw = await api.projects.me();
    return toProject(raw);
  } catch {
    return null;
  }
}

/** The Week currently in progress, or the most recent one if the
 * project has no active week at this exact instant (the orchestration
 * always starts the next one immediately, so this is mostly a defensive
 * fallback). null if no Week exists yet at all. */
export function currentWeek(project: Project): Week | null {
  const active = project.weeks.find((w) => w.status === "active");
  if (active) return active;
  return project.weeks[project.weeks.length - 1] ?? null;
}

/** Stage 2: bring your own project instead of the Manager improvising
 * one. Only works before the first task — see api.projects.createOwn. */
export async function createOwnProject(
  title: string,
  description: string,
  materialsText?: string,
  files?: File[]
): Promise<void> {
  await api.projects.createOwn(title, description, materialsText, files);
}
