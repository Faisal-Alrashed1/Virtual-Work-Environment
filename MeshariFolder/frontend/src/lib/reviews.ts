import { api, type ApiAgentType, type CareerCheckinMetricsApi, type MentorMetricsApi, type ReviewApiOut } from "./api";

export type ReviewVerdict = "approved" | "needs_changes";

export interface RubricCategory {
  key: string;
  label: string;
  score: number; // out of 5
}

export interface ReviewComment {
  id: string;
  category: string; // matches a RubricCategory.key
  content: string;
}

/** The Career Coach's career check-in (docs/TEN_AGENTS.md) — the one
 * agent besides Manager/Mentor/HR that now writes a Review, so
 * Review.agentType below can no longer assume it's always one of the
 * three defaults. */
export interface CareerCheckin {
  resumeHighlights: string[];
  suggestedFocus: string;
}

export interface Review {
  id: string;
  taskId: string | null;
  weekId: string | null;
  agentType: ApiAgentType;
  kind: "task_review" | "week_progress" | "behavioral" | "skills_rollup" | "career_checkin";
  verdict: ReviewVerdict | null; // null for anything that isn't a Mentor task review
  content: string;
  categories: RubricCategory[];
  comments: ReviewComment[];
  careerCheckin: CareerCheckin | null; // set only for kind === "career_checkin"
  createdAt: string;
}

function isMentorMetrics(
  metrics: ReviewApiOut["metrics_json"]
): metrics is MentorMetricsApi {
  return !!metrics && "verdict" in metrics;
}

function isCareerCheckinMetrics(
  metrics: ReviewApiOut["metrics_json"]
): metrics is CareerCheckinMetricsApi {
  return !!metrics && "resume_highlights" in metrics;
}

function toReview(r: ReviewApiOut): Review {
  const mentorMetrics = isMentorMetrics(r.metrics_json) ? r.metrics_json : null;
  const careerMetrics = isCareerCheckinMetrics(r.metrics_json) ? r.metrics_json : null;
  return {
    id: r.id,
    taskId: r.task_id,
    weekId: r.week_id,
    agentType: r.agent_type,
    kind: r.kind,
    verdict: mentorMetrics?.verdict ?? null,
    content: r.content,
    categories: mentorMetrics?.categories ?? [],
    comments: (mentorMetrics?.comments ?? []).map((c, i) => ({
      id: `${r.id}-c${i}`,
      category: c.category,
      content: c.content,
    })),
    careerCheckin: careerMetrics
      ? { resumeHighlights: careerMetrics.resume_highlights, suggestedFocus: careerMetrics.suggested_focus }
      : null,
    createdAt: r.created_at,
  };
}

/** Mentor's review for a single task (matches GET /tasks/{id}/review). */
export async function fetchTaskReview(taskId: string): Promise<Review | null> {
  try {
    const raw = await api.tasks.review(taskId);
    return toReview(raw);
  } catch {
    return null; // 404 — no review yet, a normal state, not an error to surface
  }
}

/** Every review (Mentor + HR rollups) for the growth timeline, oldest first. */
export async function fetchMyReviews(): Promise<Review[]> {
  const raw = await api.reviews();
  return raw.map(toReview);
}

export function averageScore(review: Review): number {
  if (review.categories.length === 0) return 0;
  const total = review.categories.reduce((sum, c) => sum + c.score, 0);
  return total / review.categories.length;
}
