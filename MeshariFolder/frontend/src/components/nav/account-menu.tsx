"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useLocale } from "@/lib/i18n/locale";

/** Consolidates a page header's email display and Log out link into one
 * control — extracted after the same "raw email span + separate Log out
 * link" pair turned up duplicated across board/workspace/meeting (and
 * would only keep spreading as more pages got a header). One shared
 * component means every page's account control looks and behaves
 * identically, and a future change (e.g. adding "Settings" as a menu
 * item) only has to happen once. */
export function AccountMenu({ email }: { email: string }) {
  const { t } = useLocale();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const initial = email.trim().charAt(0).toUpperCase() || "?";

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={t("board.accountMenu")}
        aria-expanded={open}
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded border border-border font-mono text-xs text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
      >
        {initial}
      </button>
      {open && (
        <div className="absolute end-0 top-full z-10 mt-2 w-56 rounded border border-border bg-bg-surface-raised p-2">
          <p dir="ltr" className="truncate px-2 py-1.5 font-mono text-xs text-text-muted">
            {email}
          </p>
          <div className="my-1 border-t border-border" />
          <Link
            href="/logout"
            className="block rounded px-2 py-1.5 text-sm text-text-secondary transition-colors hover:bg-bg-surface hover:text-text-primary"
          >
            {t("common.logOut")}
          </Link>
        </div>
      )}
    </div>
  );
}
