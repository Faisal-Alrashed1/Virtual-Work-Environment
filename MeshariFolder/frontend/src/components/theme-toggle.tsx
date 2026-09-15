"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/lib/theme";

/** Small icon button that flips the site theme, meant to sit inline in
 * a page header next to the other nav links/buttons.
 *
 * Renders nothing until mounted: the inline anti-flash script (see
 * layout.tsx) already applied the right theme to <html> before React
 * hydrates, but the server-rendered markup has no way to know which
 * icon that implies — so this stays blank for that one frame (matching
 * on both server and client) rather than guessing and risking a
 * hydration mismatch, then pops in with the correct icon once mounted.
 * The pop-in is a matter of a few milliseconds, invisible in practice. */
export function ThemeToggle({ className }: { className?: string }) {
  const { theme, toggleTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    // Same "fetch on mount"-shaped exception as elsewhere in the app
    // (see growth/workspace/meeting pages): this only avoids a
    // hydration mismatch between the server's theme-blind render and
    // the client's real one, it isn't synchronizing derived state.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true);
  }, []);

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={
        !mounted ? "Toggle theme" : theme === "dark" ? "Switch to light mode" : "Switch to dark mode"
      }
      className={`relative inline-flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded border border-border text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary ${className ?? ""}`}
    >
      {mounted && (
        <AnimatePresence mode="wait" initial={false}>
          <motion.span
            key={theme}
            initial={{ opacity: 0, rotate: -80, scale: 0.5 }}
            animate={{ opacity: 1, rotate: 0, scale: 1 }}
            exit={{ opacity: 0, rotate: 80, scale: 0.5 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className="flex"
          >
            {theme === "dark" ? (
              <Moon className="h-3.5 w-3.5" strokeWidth={2} />
            ) : (
              <Sun className="h-3.5 w-3.5" strokeWidth={2} />
            )}
          </motion.span>
        </AnimatePresence>
      )}
    </button>
  );
}
