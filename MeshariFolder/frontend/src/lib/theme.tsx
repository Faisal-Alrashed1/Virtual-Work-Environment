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
  return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
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
  // off) and localStorage (which the next page load's inline script
  // reads) in sync with React state after every toggle.
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    window.localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  function toggleTheme() {
    setTheme((t) => (t === "dark" ? "light" : "dark"));
  }

  return <ThemeContext.Provider value={{ theme, toggleTheme }}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within a ThemeProvider");
  return ctx;
}
