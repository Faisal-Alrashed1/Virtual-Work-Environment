// Mirrors backend/app/models.py's TrackEnum values exactly.
import type { ApiTrack } from "./api";

export const TRACKS: Record<ApiTrack, string> = {
  junior_dev: "General / Junior Developer",
  software_engineering: "Software Engineering",
  data_science_ai: "Data Science / AI",
  cybersecurity: "Cybersecurity",
  networks_infrastructure: "Networks & Infrastructure",
  information_systems: "Information Systems",
  cloud_devops: "Cloud / DevOps",
};

// Selectable tracks during onboarding — junior_dev is Stage 1's legacy
// default, not something the Stage 2 graph ever suggests or a graduate
// picks on purpose, so it's left out of the override list.
export const SELECTABLE_TRACKS: ApiTrack[] = [
  "software_engineering",
  "data_science_ai",
  "cybersecurity",
  "networks_infrastructure",
  "information_systems",
  "cloud_devops",
];
