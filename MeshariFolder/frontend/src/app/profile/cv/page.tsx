"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Upload,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  ArrowUpRight,
} from "lucide-react";
import { ApiError, useRequireAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import { useLocale } from "@/lib/i18n/locale";
import { ThemeToggle } from "@/components/theme-toggle";
import { LocaleToggle } from "@/components/locale-toggle";

type Mode = "loading" | "form" | "mid-onboarding" | "done";

export default function UpdateCvPage() {
  const { user, loading: authLoading, refreshUser } = useRequireAuth();
  const { t, locale } = useLocale();

  const [mode, setMode] = useState<Mode>("loading");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!user) return;
    api.onboarding
      .state()
      .then((s) =>
        setMode(
          ["qa", "track", "agents"].includes(s.onboarding_stage)
            ? "mid-onboarding"
            : "form",
        ),
      )
      .catch(() => setMode("form"));
  }, [user]);

  async function handleReplace() {
    if (!file) return;
    setError(null);
    setBusy(true);
    try {
      await api.cv.uploadFile(file);
      await refreshUser();
      setMode("done");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : t("cvUpdate.errors.couldntUpdate"),
      );
    } finally {
      setBusy(false);
    }
  }

  const BackArrow = locale === "ar" ? ArrowRight : ArrowLeft;

  if (authLoading || !user || mode === "loading") {
    return (
      <main className="flex min-h-screen flex-1 items-center justify-center bg-bg-base text-text-primary">
        <div className="flex items-center gap-2 rounded border border-border bg-bg-surface px-4 py-3 font-mono text-xs text-text-muted">
          <span className="h-2 w-2 animate-ping rounded-full bg-accent" />
          <span>{t("common.loading")}</span>
        </div>
      </main>
    );
  }

  return (
    <main className="relative flex min-h-screen flex-1 flex-col items-center justify-center bg-blueprint-grid px-6 py-16 text-text-primary selection:bg-accent selection:text-accent-text">
      {/* Top Engineering Header */}
      <header className="fixed inset-x-0 top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-bg-base/80 px-6 backdrop-blur-md">
        <Link
          href="/board"
          className="group flex items-center gap-2 font-mono text-xs text-text-muted transition-colors hover:text-text-primary"
        >
          <BackArrow className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5 rtl:group-hover:translate-x-0.5" />
          <span>{t("common.venv")}</span>
          <span className="text-border-strong">/</span>
          <span className="text-[10px] text-text-muted sm:inline">
            SYS.CV_UPDATE
          </span>
        </Link>
        <div className="flex items-center gap-2">
          <LocaleToggle className="bg-bg-surface" />
          <ThemeToggle className="bg-bg-surface" />
        </div>
      </header>

      {/* Main Console Box */}
      <div className="w-full max-w-lg">
        {mode === "mid-onboarding" && (
          <Panel>
            <div className="border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-3.5 w-3.5 text-accent-ink" />
                <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                  WIZARD_LOCKOUT // ACTIVE_SESSION
                </span>
              </div>
              <h1 className="mt-2 text-xl font-medium text-text-primary">
                {t("cvUpdate.midOnboardingTitle")}
              </h1>
            </div>

            <p className="mt-4 text-xs leading-relaxed text-text-secondary">
              {t("cvUpdate.midOnboardingBody")}
            </p>

            <div className="mt-6 flex items-center justify-between border-t border-border pt-4">
              <Link
                href="/board"
                className="font-mono text-xs text-text-muted transition-colors hover:text-text-primary"
              >
                {t("cvUpdate.backToBoard")}
              </Link>
              <LinkButton href="/onboarding/cv">
                {t("cvUpdate.continueOnboarding")}
              </LinkButton>
            </div>
          </Panel>
        )}

        {mode === "form" && (
          <Panel>
            <div className="border-b border-border pb-3">
              <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                PROFILE_DATA // CONTEXT_REPLACE
              </span>
              <h1 className="mt-1 text-xl font-medium text-text-primary">
                {t("cvUpdate.title")}
              </h1>
            </div>

            <p className="mt-3 text-xs leading-relaxed text-text-secondary">
              {t("cvUpdate.body")}
            </p>

            {/* Technical Dropzone */}
            <label className="mt-5 flex cursor-pointer flex-col items-center justify-center gap-2 rounded border border-dashed border-border bg-bg-surface-raised/40 p-8 text-center transition-colors hover:border-border-strong hover:bg-bg-surface-raised">
              <div className="flex h-10 w-10 items-center justify-center rounded-full border border-border bg-bg-base text-accent-ink">
                <Upload className="h-4 w-4" />
              </div>
              <span className="font-mono text-xs font-medium text-text-primary">
                {file ? file.name : t("onboarding.chooseFile")}
              </span>
              <span className="font-mono text-[10px] text-text-muted">
                FORMATS: .PDF, .DOCX, .TXT // SYSTEM_MAX: 10MB
              </span>
              <input
                type="file"
                accept=".pdf,.docx,.txt"
                className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </label>

            {error && (
              <div className="mt-4 flex items-center gap-2 rounded border border-danger/30 bg-danger/10 p-2.5 text-xs text-danger">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="mt-6 flex items-center justify-between border-t border-border pt-4">
              <Link
                href="/board"
                className="font-mono text-xs text-text-muted transition-colors hover:text-text-primary"
              >
                {t("cvUpdate.backToBoard")}
              </Link>
              <button
                type="button"
                onClick={handleReplace}
                disabled={!file || busy}
                className="inline-flex h-9 items-center justify-center rounded border border-accent bg-accent px-5 font-mono text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy ? t("cvUpdate.uploading") : t("cvUpdate.replace")}
              </button>
            </div>
          </Panel>
        )}

        {mode === "done" && (
          <Panel>
            <div className="border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-agent-mentor" />
                <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                  SYNCHRONIZATION_COMPLETE
                </span>
              </div>
              <h1 className="mt-2 text-xl font-medium text-text-primary">
                {t("cvUpdate.done")}
              </h1>
            </div>

            <p className="mt-4 text-xs leading-relaxed text-text-secondary">
              {t("cvUpdate.body")}
            </p>

            <div className="mt-4 rounded border border-border bg-bg-surface-raised/40 p-3 font-mono text-[11px] text-text-muted">
              {t("cvUpdate.doneNote")}
            </div>

            <div className="mt-6 border-t border-border pt-4">
              <LinkButton href="/board">{t("cvUpdate.backToBoard")}</LinkButton>
            </div>
          </Panel>
        )}

        {/* Footer Meta */}
        <div className="mt-6 flex items-center justify-between px-2 font-mono text-[10px] text-text-muted">
          <span>PARSING_ENGINE // ACTIVE</span>
          <span>CYCLE_SYNC: TRUE</span>
        </div>
      </div>
    </main>
  );
}

function Panel({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative rounded border border-border bg-bg-surface p-6 sm:p-7">
      {/* Corner crosshairs */}
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

      <span className="absolute inset-x-0 top-0 h-[2px] bg-accent" />
      {children}
    </div>
  );
}

function LinkButton({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className="inline-flex h-9 items-center justify-center gap-1.5 rounded border border-accent bg-accent px-5 font-mono text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong"
    >
      <span>{children}</span>
      <ArrowUpRight className="h-3.5 w-3.5" />
    </Link>
  );
}
