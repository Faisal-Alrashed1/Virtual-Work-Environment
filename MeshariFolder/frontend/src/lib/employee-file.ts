import { api } from "./api";

export interface EmployeeFile {
  skills: string[];
  strengths: string[];
  growthAreas: string[];
  summary: string | null;
}

/**
 * Each of skills_json/strengths_json/growth_areas_json is `{}` until HR's
 * first rollup, then `{"items": [...]}` — see backend/app/agents/hr.py's
 * storage note. Unwrap defensively either way.
 */
function unwrapItems(field: { items?: string[] } | undefined): string[] {
  return field?.items ?? [];
}

export async function fetchEmployeeFile(): Promise<EmployeeFile> {
  const raw = await api.employeeFile();
  return {
    skills: unwrapItems(raw.skills_json),
    strengths: unwrapItems(raw.strengths_json),
    growthAreas: unwrapItems(raw.growth_areas_json),
    summary: raw.summary_text,
  };
}
