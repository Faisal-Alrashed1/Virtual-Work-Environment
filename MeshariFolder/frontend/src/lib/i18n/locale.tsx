"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useIsomorphicLayoutEffect } from "../use-isomorphic-layout-effect";
import en from "./en";
import ar from "./ar";
import type { Dictionary } from "./en";
import { AGENT_COLOR_VAR, type AgentId, type AgentMeta } from "@/lib/agents";
import { timeAgo, timeUntil, type RelativeTimeLabels } from "@/lib/format";
import { STATUS_ORDER, type TaskStatus } from "@/lib/tasks";
import { SELECTABLE_ONLY_TRACKS, TRACK_ORDER } from "@/lib/tracks";
import type { ApiTrack } from "@/lib/api";
import type { ExtraAgent } from "@/lib/team";

export type Locale = "en" | "ar";

const STORAGE_KEY = "venv-locale";
const DICTS: Record<Locale, Dictionary> = { en, ar };
const DIR: Record<Locale, "ltr" | "rtl"> = { en: "ltr", ar: "rtl" };

/** A leaf value in the dictionary: a plain string, or an {one, other}
 * pair for count-dependent text. See en.ts's header comment for why
 * this two-form shape was chosen over full plural-rule support. */
type PluralForm = { one: string; other: string };

function isPluralForm(v: unknown): v is PluralForm {
  return typeof v === "object" && v !== null && "one" in v && "other" in v;
}

function getPath(dict: Record<string, unknown>, path: string): unknown {
  return path
    .split(".")
    .reduce<unknown>(
      (node, key) =>
        node && typeof node === "object" ? (node as Record<string, unknown>)[key] : undefined,
      dict
    );
}

function interpolate(str: string, vars?: Record<string, string | number>): string {
  if (!vars) return str;
  return str.replace(/\{(\w+)\}/g, (match, key: string) =>
    key in vars ? String(vars[key]) : match
  );
}

interface LocaleContextValue {
  locale: Locale;
  dir: "ltr" | "rtl";
  toggleLocale: () => void;
  /** Plain string lookup by dot path, e.g. t("board.welcomeBack"). Falls
   * back to the path itself if a key is somehow missing at runtime, so a
   * gap is visibly wrong rather than silently blank. */
  t: (path: string, vars?: Record<string, string | number>) => string;
  /** Count-aware lookup for a {one, other} pair, e.g.
   * tPlural("statRow.acrossReviews", count, { n: count }). */
  tPlural: (path: string, count: number, vars?: Record<string, string | number>) => string;
  /** Raw structural data (arrays of objects, etc.) that isn't a single
   * translated string — the landing page's cycle steps, orientation's
   * how-it-works cards. Not interpolated; consumers read fields off it
   * directly. */
  tRaw: <T,>(path: string) => T;
}

const LocaleContext = createContext<LocaleContextValue | null>(null);

/** Mirrors lib/theme.tsx's readAppliedTheme: reads whatever the anti-
 * flash inline script (layout.tsx's <head>) already applied to
 * <html lang/dir>. Only ever called from a layout effect, after
 * hydration commits — never as the initial useState value, which would
 * make the client's first render (the one hydration compares against
 * the server-rendered HTML) disagree with the server for any non-English
 * visitor. See ThemeProvider's identical fix for the full reasoning. */
function readAppliedLocale(): Locale {
  if (typeof document === "undefined") return "en";
  // The stored choice is the source of truth, same rule as the anti-flash
  // script. Not <html lang>: the effect below sets that from state, and on
  // the first mount (twice under dev StrictMode) state is still "en", so
  // re-reading the attribute picked the reset value and Arabic was lost on
  // every reload.
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "en" || stored === "ar") return stored;
  } catch {
    // storage unavailable — fall through to the browser language
  }
  return /^ar\b/.test(navigator.language || "") ? "ar" : "en";
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  // Must start at "en" — the same default the server always renders,
  // since it has no access to localStorage/navigator.language. See the
  // comment above and ThemeProvider's matching fix.
  const [locale, setLocale] = useState<Locale>("en");

  // Adopts the anti-flash script's actual applied locale after
  // hydration commits, synchronously before paint — no visible flash,
  // and never compared against the server-rendered markup.
  useIsomorphicLayoutEffect(() => {
    const applied = readAppliedLocale();
    setLocale((current) => (current === applied ? current : applied));
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("lang", locale);
    document.documentElement.setAttribute("dir", DIR[locale]);
  }, [locale]);

  // Persist only on an explicit toggle. Persisting from the effect above
  // also saved the initial "en" on every page load, overwriting a stored
  // "ar" before it was adopted.
  function toggleLocale() {
    const next: Locale = locale === "en" ? "ar" : "en";
    setLocale(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // storage unavailable — the choice just won't survive a reload
    }
  }

  function t(path: string, vars?: Record<string, string | number>): string {
    const raw = getPath(DICTS[locale], path);
    if (typeof raw !== "string") return path;
    return interpolate(raw, vars);
  }

  function tPlural(
    path: string,
    count: number,
    vars?: Record<string, string | number>
  ): string {
    const raw = getPath(DICTS[locale], path);
    if (!isPluralForm(raw)) return path;
    return interpolate(count === 1 ? raw.one : raw.other, vars);
  }

  function tRaw<T>(path: string): T {
    return getPath(DICTS[locale], path) as T;
  }

  return (
    <LocaleContext.Provider value={{ locale, dir: DIR[locale], toggleLocale, t, tPlural, tRaw }}>
      {children}
    </LocaleContext.Provider>
  );
}

export function useLocale(): LocaleContextValue {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error("useLocale must be used within a LocaleProvider");
  return ctx;
}

/** The three default agents' name/role/description, translated for the
 * current locale. A hook (not a plain export) because the text is
 * locale-dependent — call it once at the top of a component, same as
 * any other hook, then pass the result down to any plain helper (like
 * resolveAgentDisplay below) that needs it inside a loop. */
export function useAgents(): Record<AgentId, AgentMeta> {
  const { t } = useLocale();
  function build(id: AgentId): AgentMeta {
    return {
      id,
      name: t(`agents.${id}.name`),
      role: t(`agents.${id}.role`),
      description: t(`agents.${id}.description`),
      colorVar: AGENT_COLOR_VAR[id],
    };
  }
  return {
    manager: build("manager"),
    mentor: build("mentor"),
    hr: build("hr"),
  };
}

export interface AgentDisplay {
  name: string;
  role: string;
  colorVar: string | null;
}

/** Plain function, not a hook — safe to call inside a .map() over a
 * message list or agent roster. Takes the already-resolved `agents`
 * dict (from useAgents(), called once by the component) rather than
 * looking anything up itself. Looks up an agent id that might be one
 * of the fixed default three or one of the graduate's extra roster
 * agents — the catalog can grow, so this never assumes a closed set. */
export function resolveAgentDisplay(
  id: string,
  agents: Record<AgentId, AgentMeta>,
  extraAgents: ExtraAgent[],
  extraNames: Record<string, string> = {}
): AgentDisplay {
  if (id in agents) {
    const m = agents[id as AgentId];
    return { name: m.name, role: m.role, colorVar: m.colorVar };
  }
  const extra = extraAgents.find((a) => a.id === id);
  return { name: extraNames[id] ?? extra?.name ?? id, role: extra?.description ?? "", colorVar: null };
}

/** The optional agents' names in the current locale, keyed by catalog id —
 * pass to resolveAgentDisplay. Unknown ids fall back to the catalog name. */
export function useExtraAgentNames(): Record<string, string> {
  const { tRaw } = useLocale();
  return tRaw<Record<string, string>>("extraAgentNames");
}

/** timeAgo / timeUntil in the current locale ("3h ago" / "قبل 3 ساعة").
 * Call once at the top of a component, like useAgents. */
export function useRelativeTime(): {
  timeAgo: (iso: string) => string;
  timeUntil: (iso: string) => string;
} {
  const { tRaw } = useLocale();
  const labels = tRaw<RelativeTimeLabels>("time");
  return {
    timeAgo: (iso) => timeAgo(iso, labels),
    timeUntil: (iso) => timeUntil(iso, labels),
  };
}

/** The four task-status labels (To do / In progress / Submitted /
 * Reviewed), translated. */
export function useStatusLabels(): Record<TaskStatus, string> {
  const { t } = useLocale();
  return Object.fromEntries(
    STATUS_ORDER.map((s) => [s, t(`taskStatus.${s}`)])
  ) as Record<TaskStatus, string>;
}

/** The seven track labels, translated, keyed by the backend's ApiTrack
 * enum value. */
export function useTrackLabels(): Record<ApiTrack, string> {
  const { t } = useLocale();
  return Object.fromEntries(
    TRACK_ORDER.map((tr) => [tr, t(`tracks.${tr}`)])
  ) as Record<ApiTrack, string>;
}

// Re-exported so call sites that only need the six selectable tracks
// (onboarding's track-override dropdown) don't also need to import
// from lib/tracks directly.
export { SELECTABLE_ONLY_TRACKS };
