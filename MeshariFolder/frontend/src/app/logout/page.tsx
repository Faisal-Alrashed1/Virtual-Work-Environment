"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { LogOut, CheckCircle2, ArrowLeft, ArrowRight } from "lucide-react";
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
  const { t, locale } = useLocale();
  const [signedOut, setSignedOut] = useState(false);

  function confirm() {
    clearSession(); // clears the token in place; we show the sign-off below
    setSignedOut(true);
  }

  const BackArrow = locale === "ar" ? ArrowRight : ArrowLeft;

  return (
    <main className="relative flex min-h-screen flex-1 flex-col items-center justify-center bg-blueprint-grid px-6 py-12 text-text-primary selection:bg-accent selection:text-accent-text">
      {/* Top utility bar */}
      <header className="fixed inset-x-0 top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-bg-base/80 px-6 backdrop-blur-md">
        <Link
          href="/"
          className="group flex items-center gap-2 font-mono text-xs text-text-muted transition-colors hover:text-text-primary"
        >
          <BackArrow className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5 rtl:group-hover:translate-x-0.5" />
          <span>{t("common.venv")}</span>
          <span className="hidden text-border-strong sm:inline">/</span>
          <span className="hidden text-[10px] text-text-muted sm:inline">
            SYS.SESSION
          </span>
        </Link>
        <div className="flex items-center gap-2">
          <LocaleToggle className="bg-bg-surface" />
          <ThemeToggle className="bg-bg-surface" />
        </div>
      </header>

      {/* Main Container */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: "easeOut" }}
        className="relative w-full max-w-sm rounded border border-border bg-bg-surface p-6 sm:p-7"
      >
        {/* Technical Corner Markers */}
        <div className="pointer-events-none absolute -start-[5px] -top-[5px] font-mono text-xs leading-none text-text-muted">
          +
        </div>
        <div className="pointer-events-none absolute -end-[5px] -top-[5px] font-mono text-xs leading-none text-text-muted">
          +
        </div>
        <div className="pointer-events-none absolute -bottom-[5px] -start-[5px] font-mono text-xs leading-none text-text-muted">
          +
        </div>
        <div className="pointer-events-none absolute -bottom-[5px] -end-[5px] font-mono text-xs leading-none text-text-muted">
          +
        </div>

        {/* Top hairline indicator */}
        <span className="absolute inset-x-0 top-0 h-[2px] bg-accent" />

        <AnimatePresence mode="wait">
          {!signedOut ? (
            <motion.div
              key="confirm"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
            >
              {/* Status Header */}
              <div className="border-b border-border pb-4">
                <div className="flex items-center justify-between font-mono text-[10px] uppercase tracking-wider text-text-muted">
                  <span className="flex items-center gap-1.5">
                    <LogOut className="h-3 w-3 text-accent-ink" />
                    TERMINATION_REQUEST
                  </span>
                  <span>OP_CODE_0x7</span>
                </div>
                <h1 className="mt-3 text-xl font-medium text-text-primary">
                  {t("logout.signOutQuestion")}
                </h1>
              </div>

              {/* Body Content */}
              <div className="mt-4">
                <p className="text-sm leading-relaxed text-text-secondary">
                  {user
                    ? t("logout.signedInAs", { email: user.email })
                    : t("logout.aboutToSignOut")}
                </p>

                {user?.email && (
                  <div className="mt-3 rounded border border-border bg-bg-base/70 px-3 py-2 text-start">
                    <span className="block font-mono text-[10px] uppercase text-text-muted">
                      ACTIVE_IDENTITY:
                    </span>
                    <span
                      dir="ltr"
                      className="block truncate font-mono text-xs text-text-primary"
                    >
                      {user.email}
                    </span>
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="mt-6 flex flex-col gap-2.5">
                <button
                  type="button"
                  onClick={confirm}
                  className="inline-flex h-9 items-center justify-center rounded border border-accent bg-accent px-4 font-mono text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong"
                >
                  {t("logout.confirm")}
                </button>
                <button
                  type="button"
                  onClick={() => router.back()}
                  className="inline-flex h-9 items-center justify-center rounded border border-border bg-bg-base px-4 font-mono text-xs font-medium text-text-secondary transition-colors hover:border-border-strong hover:bg-bg-surface-raised hover:text-text-primary"
                >
                  {t("logout.staySignedIn")}
                </button>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="done"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="text-center"
            >
              {/* Completion Icon */}
              <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full border border-border bg-bg-base text-accent-ink">
                <CheckCircle2 className="h-5 w-5" strokeWidth={1.75} />
              </div>

              <div className="mt-4 border-b border-border pb-4">
                <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                  SESSION // TERMINATED
                </span>
                <h1 className="mt-1 text-xl font-medium text-text-primary">
                  {t("logout.signedOutTitle")}
                </h1>
              </div>

              <p className="mt-4 text-sm leading-relaxed text-text-secondary">
                {t("logout.signedOutBody")}
              </p>

              <div className="mt-6">
                <Link
                  href="/login"
                  className="inline-flex h-9 w-full items-center justify-center rounded border border-accent bg-accent px-5 font-mono text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong"
                >
                  {t("logout.signBackIn")}
                </Link>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Footer Meta */}
        <div className="mt-6 flex items-center justify-between border-t border-border/60 pt-3 font-mono text-[10px] text-text-muted">
          <span>CLEAR_SESSION // OK</span>
          <span>DISCONNECTED</span>
        </div>
      </motion.div>
    </main>
  );
}
