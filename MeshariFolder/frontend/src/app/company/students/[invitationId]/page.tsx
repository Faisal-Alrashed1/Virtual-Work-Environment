"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  GraduationCap,
  Calendar,
  CheckCircle2,
  Activity,
  AlertCircle,
  FileCheck2,
  Users,
} from "lucide-react";
import { useRequireAuth, ApiError } from "@/lib/auth-context";
import {
  fetchCompanyStudentDetail,
  type CompanyStudentDetail,
} from "@/lib/company";
import { useLocale } from "@/lib/i18n/locale";
import { ThemeToggle } from "@/components/theme-toggle";
import { LocaleToggle } from "@/components/locale-toggle";
import { AccountMenu } from "@/components/nav/account-menu";

// One hired student's week-by-week detail (docs/STAGE3_COMPANY_RAG.md) —
// each week's tasks plus whichever end-of-week reviews exist for it so
// far (the Manager's progress review, HR's behavioral review). This IS
// the "end-of-week report": the same reviews the weekly cycle already
// writes, not a second report generated just for this screen.
export default function CompanyStudentDetailPage() {
  const { user, loading: authLoading } = useRequireAuth();
  const params = useParams<{ invitationId: string }>();
  const { t, locale } = useLocale();

  const [detail, setDetail] = useState<CompanyStudentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    fetchCompanyStudentDetail(params.invitationId)
      .then(setDetail)
      .catch((err) =>
        setError(
          err instanceof ApiError ? err.message : t("common.genericError"),
        ),
      )
      .finally(() => setLoading(false));
  }, [user, params.invitationId, t]);

  const BackArrow = locale === "ar" ? ArrowRight : ArrowLeft;

  if (authLoading || !user || loading) {
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
    <main className="grid h-dvh grid-rows-[auto_1fr] bg-bg-base text-text-primary selection:bg-accent selection:text-accent-text">
      {/* Top Architecture Navigation Bar */}
      <header className="z-20 flex h-14 items-center justify-between border-b border-border bg-bg-surface/90 px-6 backdrop-blur-md">
        <div className="flex items-center gap-4">
          <Link
            href="/company/students"
            className="group flex items-center gap-2 font-mono text-xs text-text-muted transition-colors hover:text-text-primary"
          >
            <BackArrow className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5 rtl:group-hover:translate-x-0.5" />
            <span>{t("common.venv")}</span>
            <span className="text-border-strong">/</span>
            <span>{t("company.studentsTitle")}</span>
            <span className="text-border-strong">/</span>
            <span className="text-[10px] text-text-muted transition-colors group-hover:text-text-secondary">
              STUDENT_REPORT
            </span>
          </Link>

          <div className="hidden items-center gap-2 border-s border-border ps-4 sm:flex">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            <h1 className="font-mono text-xs font-medium uppercase tracking-wider text-text-primary">
              {detail?.studentName}
            </h1>
          </div>
        </div>

        {/* Global Toolbar Cluster */}
        <div className="flex items-center gap-3">
          <Link
            href="/company/students"
            className="inline-flex h-8 items-center gap-1.5 rounded border border-border bg-bg-base px-3 font-mono text-xs text-text-secondary transition-colors hover:border-border-strong hover:bg-bg-surface hover:text-text-primary"
          >
            <Users className="h-3.5 w-3.5" />
            <span>{t("company.studentsTitle")}</span>
          </Link>

          <div className="mx-1 h-4 border-s border-border" />

          <AccountMenu email={user.email} />
          <LocaleToggle className="bg-bg-base" />
          <ThemeToggle className="bg-bg-base" />
        </div>
      </header>

      {/* Main Stream Area */}
      <div className="thin-scrollbar overflow-y-auto">
        <div className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-8">
          {/* Header Candidate Snapshot Card */}
          {detail && (
            <div className="relative rounded border border-border bg-bg-surface p-5 sm:p-6">
              <span className="absolute inset-x-0 top-0 h-[2px] bg-accent" />
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
                <div className="flex items-center gap-2">
                  <GraduationCap className="h-4 w-4 text-accent-ink" />
                  <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                    CANDIDATE_AUDIT // WEEKLY_EVALUATION
                  </span>
                </div>
                <span className="font-mono text-[10px] text-text-muted">
                  INVITATION_ID: {params.invitationId.slice(0, 8)}
                </span>
              </div>

              <div className="mt-4 flex flex-wrap items-baseline justify-between gap-2">
                <div>
                  <h2 className="text-xl font-medium tracking-tight text-text-primary">
                    {detail.studentName}
                  </h2>
                  <p className="mt-1 font-mono text-xs text-text-secondary">
                    {detail.jobTitle}
                    {detail.companyProjectTitle && (
                      <span className="text-text-muted">
                        {" "}
                        · {detail.companyProjectTitle}
                      </span>
                    )}
                  </p>
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 rounded border border-danger/30 bg-danger/10 p-3 font-mono text-xs text-danger">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {detail && detail.weeks.length === 0 && (
            <div className="rounded border border-dashed border-border bg-bg-surface/50 p-8 text-center">
              <Calendar className="mx-auto h-6 w-6 text-text-muted" />
              <p className="mt-2 text-xs text-text-muted">
                {t("company.notStartedYet")}
              </p>
            </div>
          )}

          {/* Week Cadence Feed */}
          {detail?.weeks
            .slice()
            .reverse()
            .map((week) => (
              <div
                key={week.weekNumber}
                className="relative rounded border border-border bg-bg-surface p-6"
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

                {/* Week Header */}
                <div className="flex items-center justify-between border-b border-border pb-3">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-semibold uppercase text-text-primary">
                      {t("company.weekLabel", {
                        number: String(week.weekNumber),
                      })}
                    </span>
                  </div>

                  <span
                    className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 font-mono text-[10px] ${
                      week.status === "active"
                        ? "border-accent/40 bg-accent/10 text-accent-ink"
                        : "border-border bg-bg-base text-text-muted"
                    }`}
                  >
                    {week.status === "active" ? (
                      <Activity className="h-2.5 w-2.5" />
                    ) : (
                      <CheckCircle2 className="h-2.5 w-2.5 text-agent-mentor" />
                    )}
                    <span>
                      {week.status === "active"
                        ? t("company.weekActive")
                        : t("company.weekCompleted")}
                    </span>
                  </span>
                </div>

                {/* Task Item Logs */}
                <div className="mt-4 flex flex-col gap-2">
                  <span className="font-mono text-[10px] uppercase text-text-muted">
                    SUBTASK_PROGRESSION:
                  </span>
                  {week.tasks.map((task) => (
                    <div
                      key={task.id}
                      className="flex items-center justify-between rounded border border-border bg-bg-surface-raised px-3.5 py-2.5 transition-colors hover:border-border-strong"
                    >
                      <p className="text-xs font-medium text-text-primary">
                        {task.title}
                      </p>
                      <span className="rounded border border-border bg-bg-base px-2 py-0.5 font-mono text-[9px] uppercase text-text-muted">
                        {task.status}
                      </span>
                    </div>
                  ))}
                </div>

                {/* End-of-Week Review Evaluations */}
                {week.reviews.length > 0 && (
                  <div className="mt-5 flex flex-col gap-2.5 border-t border-border/60 pt-4">
                    <span className="font-mono text-[10px] uppercase text-text-muted">
                      EVALUATION_SYNTHESIS:
                    </span>
                    {week.reviews.map((review) => (
                      <div
                        key={review.id}
                        className="rounded border border-border bg-bg-surface-raised/70 p-3.5 border-s-2 border-s-accent"
                      >
                        <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase text-text-muted">
                          <FileCheck2 className="h-3 w-3 text-accent-ink" />
                          <span>
                            {review.kind === "week_progress"
                              ? t("company.weekProgressReview")
                              : t("company.behavioralReview")}
                          </span>
                        </div>
                        <p className="mt-1.5 text-xs leading-relaxed text-text-secondary">
                          {review.content}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}

          {/* Footer Back Link */}
          <div className="border-t border-border pt-4">
            <Link
              href="/company/students"
              className="group inline-flex items-center gap-1.5 font-mono text-xs text-text-muted transition-colors hover:text-text-primary"
            >
              <BackArrow className="h-3 w-3 transition-transform group-hover:-translate-x-0.5 rtl:group-hover:translate-x-0.5" />
              <span>{t("company.studentsTitle")}</span>
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
