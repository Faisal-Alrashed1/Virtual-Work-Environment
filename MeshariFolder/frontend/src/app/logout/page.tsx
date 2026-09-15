"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { useAuth } from "@/lib/auth-context";
import { useLocale } from "@/lib/i18n/locale";
import { ThemeToggle } from "@/components/theme-toggle";
import { LocaleToggle } from "@/components/locale-toggle";

/**
 * A deliberate sign-off screen rather than an instant token-clear + bounce.
 * Two states: confirm (are you sure?) and done (signed out, with a way back
 * in). Keeps the same blueprint-grid backdrop as the landing/login pages so
 * the whole logged-out edge of the app feels like one place.
 */
export default function LogoutPage() {
  const { user, clearSession } = useAuth();
  const router = useRouter();
  const { t } = useLocale();
  const [signedOut, setSignedOut] = useState(false);

  function confirm() {
    clearSession(); // clears the token in place; we show the sign-off below
    setSignedOut(true);
  }

  return (
    <main className="bg-blueprint-grid flex flex-1 flex-col items-center justify-center px-6">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: "easeOut" }}
        className="w-full max-w-sm rounded border border-border bg-bg-surface p-6 text-center"
      >
        <div className="flex items-center justify-between">
          <Link
            href="/"
            className="font-mono text-xs text-text-muted hover:text-text-secondary"
          >
            {t("common.venv")}
          </Link>
          <div className="flex items-center gap-2">
            <LocaleToggle />
            <ThemeToggle />
          </div>
        </div>

        {!signedOut ? (
          <>
            <h1 className="mt-2 text-xl font-medium text-text-primary">
              {t("logout.signOutQuestion")}
            </h1>
            <p className="mt-2 text-sm leading-relaxed text-text-secondary">
              {user
                ? t("logout.signedInAs", { email: user.email })
                : t("logout.aboutToSignOut")}
            </p>
            <div className="mt-6 flex flex-col gap-2">
              <button
                type="button"
                onClick={confirm}
                className="rounded border border-accent bg-accent px-4 py-2.5 text-sm font-medium text-accent-text transition-colors hover:bg-accent-strong"
              >
                {t("logout.confirm")}
              </button>
              <button
                type="button"
                onClick={() => router.back()}
                className="rounded border border-border px-4 py-2.5 text-sm text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
              >
                {t("logout.staySignedIn")}
              </button>
            </div>
          </>
        ) : (
          <>
            <h1 className="mt-2 text-xl font-medium text-text-primary">
              {t("logout.signedOutTitle")}
            </h1>
            <p className="mt-2 text-sm leading-relaxed text-text-secondary">
              {t("logout.signedOutBody")}
            </p>
            <Link
              href="/login"
              className="mt-6 inline-block rounded border border-accent bg-accent px-5 py-2.5 text-sm font-medium text-accent-text transition-colors hover:bg-accent-strong"
            >
              {t("logout.signBackIn")}
            </Link>
          </>
        )}
      </motion.div>
    </main>
  );
}
