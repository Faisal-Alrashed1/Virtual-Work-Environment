import en from "./i18n/en";

export type RelativeTimeLabels = typeof en.time;

/** The API sends UTC timestamps with no timezone suffix (the backend stores
 * naive `datetime.utcnow()`), and JS parses a suffix-less ISO date-time as
 * *local* time — which put every time 3 hours off in Riyadh ("3h ago" for
 * something just created). Read suffix-less date-times as UTC. */
export function parseServerTime(iso: string): Date {
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(iso);
  return new Date(iso.includes("T") && !hasZone ? `${iso}Z` : iso);
}

function fill(template: string, n: number): string {
  return template.replace("{n}", String(n));
}

/** `labels` comes from the current locale's `time` dictionary — components
 * get it bound via useRelativeTime() in lib/i18n/locale.tsx. Defaults to
 * English for any caller outside the locale context. */
export function timeAgo(iso: string, labels: RelativeTimeLabels = en.time): string {
  const diffMs = Date.now() - parseServerTime(iso).getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return labels.justNow;
  if (minutes < 60) return fill(labels.minutesAgo, minutes);
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return fill(labels.hoursAgo, hours);
  return fill(labels.daysAgo, Math.floor(hours / 24));
}

/** Inverse of timeAgo, for deadlines/target dates instead of past events. */
export function timeUntil(iso: string, labels: RelativeTimeLabels = en.time): string {
  const diffMs = parseServerTime(iso).getTime() - Date.now();
  if (diffMs <= 0) return labels.pastDue;
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 60) return fill(labels.inMinutes, Math.max(minutes, 1));
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return fill(labels.inHours, hours);
  return fill(labels.inDays, Math.floor(hours / 24));
}
