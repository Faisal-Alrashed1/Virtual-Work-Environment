import { api, type DashboardApiOut } from "./api";

export interface Dashboard {
  tasksCompleted: number;
  tasksTotal: number;
  /** null when no completed task has both a deadline and a completion yet
   * — the UI shows "—" rather than a misleading 0% or 100%. */
  onTimeRate: number | null;
  averageScore: number | null;
  reviewsCount: number;
  weeksCompleted: number;
  weeksTotal: number;
  hasActiveProject: boolean;
}

function toDashboard(d: DashboardApiOut): Dashboard {
  return {
    tasksCompleted: d.tasks_completed,
    tasksTotal: d.tasks_total,
    onTimeRate: d.on_time_rate,
    averageScore: d.average_score,
    reviewsCount: d.reviews_count,
    weeksCompleted: d.weeks_completed,
    weeksTotal: d.weeks_total,
    hasActiveProject: d.has_active_project,
  };
}

export async function fetchDashboard(): Promise<Dashboard> {
  return toDashboard(await api.dashboard());
}
