"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useIsomorphicLayoutEffect } from "./use-isomorphic-layout-effect";

export type Theme = "dark" | "light";

const STORAGE_KEY = "venv-theme";

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function readAppliedTheme(): Theme {
  if (typeof document === "undefined") return "dark";
  // Same rule as the anti-flash script: stored choice, else the OS
  // preference. Not <html data-theme> — the effect below sets that from
  // state, which is still "dark" on the first mount (twice under dev
  // StrictMode), so re-reading it lost a saved "light" on reload.
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    // storage unavailable — fall through to the OS preference
  }
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  // Must start at the same value the server always renders with ("dark"
  // — the server has no access to localStorage/matchMedia) so the
  // client's *first* render, which React compares against the
  // server-rendered HTML during hydration, matches exactly. Reading the
  // anti-flash script's already-applied value here instead (as an
  // earlier version did) makes that first client render disagree with
  // the server output for any light-mode visitor — a hydration
  // mismatch, not just a harmless one-frame flash on <html> the way the
  // inline script itself is.
  const [theme, setTheme] = useState<Theme>("dark");

  // Runs after hydration commits, synchronously before paint — adopts
  // whatever the anti-flash script actually applied, with no visible
  // flash and, critically, without this update ever being compared
  // against the server-rendered markup (only the initial render is).
  useIsomorphicLayoutEffect(() => {
    const applied = readAppliedTheme();
    setTheme((current) => (current === applied ? current : applied));
  }, []);

  // Keep <html data-theme> (which every CSS variable in globals.css keys
  // off) in sync with React state.
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  // Persist only on an explicit toggle (read by the next page load's inline
  // script). Persisting from the effect above also saved the initial
  // "dark" on every load, overwriting a stored "light".
  function toggleTheme() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // storage unavailable — the choice just won't survive a reload
    }
  }

  return <ThemeContext.Provider value={{ theme, toggleTheme }}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within a ThemeProvider");
  return ctx;
}
