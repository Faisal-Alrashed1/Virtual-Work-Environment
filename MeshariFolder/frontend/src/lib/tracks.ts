// Mirrors backend/app/models.py's TrackEnum values exactly.
import type { ApiTrack } from "./api";

// Display labels used to live here as a static English Record — they're
// translated now, under `tracks.*` in lib/i18n/en.ts and ar.ts. This
// file keeps only the locale-independent enum ordering. Use
// lib/i18n/locale.tsx's useTrackLabels() hook for the translated text.
export const TRACK_ORDER: ApiTrack[] = [
  "junior_dev",
  "software_engineering",
  "data_science_ai",
  "cybersecurity",
  "networks_infrastructure",
  "information_systems",
  "cloud_devops",
];

// Selectable tracks during onboarding — junior_dev is Stage 1's legacy
// default, not something the Stage 2 graph ever suggests or a graduate
// picks on purpose, so it's left out of the override list.
export const SELECTABLE_ONLY_TRACKS: ApiTrack[] = [
  "software_engineering",
  "data_science_ai",
  "cybersecurity",
  "networks_infrastructure",
  "information_systems",
  "cloud_devops",
];
