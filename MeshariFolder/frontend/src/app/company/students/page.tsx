"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  Users,
  ArrowUpRight,
  AlertCircle,
  GraduationCap,
  Activity,
  Clock,
} from "lucide-react";
import { useRequireAuth, ApiError } from "@/lib/auth-context";
import { fetchCompanyStudents, type CompanyStudent } from "@/lib/company";
import { useLocale } from "@/lib/i18n/locale";
import { ThemeToggle } from "@/components/theme-toggle";
import { LocaleToggle } from "@/components/locale-toggle";
import { AccountMenu } from "@/components/nav/account-menu";

// The company's live roster (docs/STAGE3_COMPANY_RAG.md) — everyone who
// has actually accepted an invitation, with a quick snapshot of where
// they are. Click through for the week-by-week detail and reviews.
export default function CompanyStudentsPage() {
  const { user, loading: authLoading } = useRequireAuth();
  const { t, locale } = useLocale();

  const [students, setStudents] = useState<CompanyStudent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    fetchCompanyStudents()
      .then(setStudents)
      .catch((err) =>
        setError(
          err instanceof ApiError ? err.message : t("common.genericError"),
        ),
      )
      .finally(() => setLoading(false));
  }, [user, t]);

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
            href="/company"
            className="group flex items-center gap-2 font-mono text-xs text-text-muted transition-colors hover:text-text-primary"
          >
            <BackArrow className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5 rtl:group-hover:translate-x-0.5" />
            <span>{t("common.venv")}</span>
            <span className="text-border-strong">/</span>
            <span>{t("company.nav")}</span>
            <span className="text-border-strong">/</span>
            <span className="text-[10px] text-text-muted transition-colors group-hover:text-text-secondary">
              STUDENT_ROSTER
            </span>
          </Link>

          <div className="hidden items-center gap-2 border-s border-border ps-4 sm:flex">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            <h1 className="font-mono text-xs font-medium uppercase tracking-wider text-text-primary">
              {t("company.studentsTitle")}
            </h1>
          </div>
        </div>

        {/* Global Toolbar Cluster */}
        <div className="flex items-center gap-3">
          <AccountMenu email={user.email} />
          <LocaleToggle className="bg-bg-base" />
          <ThemeToggle className="bg-bg-base" />
        </div>
      </header>

      {/* Main Viewport Content */}
      <div className="thin-scrollbar overflow-y-auto">
        <div className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-10">
          {/* Header Metadata Summary Card */}
          <div className="relative rounded border border-border bg-bg-surface p-6 sm:p-7">
            <span className="absolute inset-x-0 top-0 h-[2px] bg-accent" />
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <Users className="h-4 w-4 text-accent-ink" />
                <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                  TALENT_ROSTER // COHORT_REGISTRY
                </span>
              </div>
              <span className="font-mono text-[10px] text-text-muted">
                ACTIVE_TALENT: {students.length}
              </span>
            </div>

            <div className="mt-4">
              <h2 className="text-xl font-medium tracking-tight text-text-primary">
                {t("company.studentsTitle")}
              </h2>
              <p className="mt-1 text-xs leading-relaxed text-text-secondary">
                {t("company.newJobTitleBody")}
              </p>
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 rounded border border-danger/30 bg-danger/10 p-3 font-mono text-xs text-danger">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Students Directory */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between border-b border-border pb-2">
              <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                REGISTERED_CANDIDATES
              </span>
              <span className="font-mono text-[10px] text-text-muted">
                STAGE_03 // VERIFIED
              </span>
            </div>

            {students.length === 0 ? (
              <div className="rounded border border-dashed border-border bg-bg-surface/50 p-10 text-center font-mono text-xs text-text-muted">
                {t("company.noStudents")}
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                {students.map((s) => (
                  <Link
                    key={s.invitationId}
                    href={`/company/students/${s.invitationId}`}
                    className="group relative flex flex-wrap items-center justify-between gap-4 rounded border border-border bg-bg-surface p-4 transition-colors hover:border-border-strong hover:bg-bg-surface-raised"
                  >
                    <div className="flex items-start gap-3.5">
                      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded border border-border bg-bg-base text-accent-ink">
                        <GraduationCap className="h-4 w-4" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="text-xs font-semibold text-text-primary group-hover:text-accent-ink transition-colors">
                            {s.studentName}
                          </p>
                          <ArrowUpRight className="h-3 w-3 text-text-muted transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                        </div>
                        <p
                          dir="ltr"
                          className="mt-0.5 text-start font-mono text-[11px] text-text-muted"
                        >
                          {s.studentEmail}
                        </p>
                        <p className="mt-1 font-mono text-[11px] text-text-secondary">
                          {s.jobTitle}
                          {s.companyProjectTitle && (
                            <span className="text-text-muted">
                              {" "}
                              · {s.companyProjectTitle}
                            </span>
                          )}
                        </p>
                      </div>
                    </div>

                    <div className="flex flex-col items-end gap-1.5">
                      {s.currentWeekNumber ? (
                        <span className="inline-flex items-center gap-1.5 rounded border border-accent/40 bg-accent/10 px-2.5 py-0.5 font-mono text-[10px] text-accent-ink">
                          <Activity className="h-2.5 w-2.5" />
                          <span>
                            {t("company.weekLabel", {
                              number: String(s.currentWeekNumber),
                            })}
                          </span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 rounded border border-border bg-bg-base px-2.5 py-0.5 font-mono text-[10px] text-text-muted">
                          <Clock className="h-2.5 w-2.5" />
                          <span>{t("company.notStartedYet")}</span>
                        </span>
                      )}

                      {s.projectTitle && (
                        <p className="font-mono text-[10px] text-text-muted">
                          {s.projectTitle}
                        </p>
                      )}
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>

          {/* Footer Back Link */}
          <div className="border-t border-border pt-4">
            <Link
              href="/company"
              className="group inline-flex items-center gap-1.5 font-mono text-xs text-text-muted transition-colors hover:text-text-primary"
            >
              <BackArrow className="h-3 w-3 transition-transform group-hover:-translate-x-0.5 rtl:group-hover:translate-x-0.5" />
              <span>{t("company.nav")}</span>
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
