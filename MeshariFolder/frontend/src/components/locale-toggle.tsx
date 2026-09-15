"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useLocale } from "@/lib/i18n/locale";

/** Small text toggle that flips the site language, meant to sit inline
 * in a page header next to ThemeToggle. Deliberately a text label
 * ("EN"/"عربي") rather than a flag icon or globe glyph — a flag implies
 * a country, not a language, and this app has exactly two language
 * states to flip between, not a long list to pick from.
 *
 * Same mounted-gate as ThemeToggle and for the same reason: the
 * anti-flash script in layout.tsx already set the real <html lang>
 * before hydration, but server-rendered markup can't know which label
 * that implies, so this stays blank for one frame on both sides rather
 * than risking a mismatch. */
export function LocaleToggle({ className }: { className?: string }) {
  const { locale, toggleLocale, t } = useLocale();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    // Same avoid-a-hydration-mismatch exception as ThemeToggle — see
    // its comment for why this is the "subscribe" case the rule allows.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true);
  }, []);

  return (
    <button
      type="button"
      onClick={toggleLocale}
      aria-label={t("locale.toggleLabel")}
      className={`relative inline-flex h-8 min-w-8 shrink-0 items-center justify-center overflow-hidden rounded border border-border px-2 font-mono text-[11px] text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary ${className ?? ""}`}
    >
      {mounted && (
        <AnimatePresence mode="wait" initial={false}>
          <motion.span
            key={locale}
            dir="ltr"
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
          >
            {locale === "en" ? "AR" : "EN"}
          </motion.span>
        </AnimatePresence>
      )}
    </button>
  );
}
