/** The API sends UTC timestamps with no timezone suffix (the backend stores
 * naive `datetime.utcnow()`), and JS parses a suffix-less ISO date-time as
 * *local* time — which put every time 3 hours off in Riyadh ("3h ago" for
 * something just created). Read suffix-less date-times as UTC. */
export function parseServerTime(iso: string): Date {
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(iso);
  return new Date(iso.includes("T") && !hasZone ? `${iso}Z` : iso);
}

export function timeAgo(iso: string): string {
  const diffMs = Date.now() - parseServerTime(iso).getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

/** Inverse of timeAgo, for deadlines/target dates instead of past events. */
export function timeUntil(iso: string): string {
  const diffMs = parseServerTime(iso).getTime() - Date.now();
  if (diffMs <= 0) return "past due";
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 60) return `in ${Math.max(minutes, 1)}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `in ${hours}h`;
  const days = Math.floor(hours / 24);
  return `in ${days}d`;
}
