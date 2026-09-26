"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Building2,
  Users,
  Copy,
  Check,
  Plus,
  ArrowUpRight,
  Briefcase,
  AlertCircle,
} from "lucide-react";
import { useRequireAuth, ApiError } from "@/lib/auth-context";
import {
  createJobTitle,
  fetchJobTitles,
  fetchMyCompany,
  type JobTitle,
  type Organization,
} from "@/lib/company";
import { useLocale } from "@/lib/i18n/locale";
import { ThemeToggle } from "@/components/theme-toggle";
import { LocaleToggle } from "@/components/locale-toggle";
import { AccountMenu } from "@/components/nav/account-menu";

// The company dashboard (docs/STAGE3_COMPANY_RAG.md): the org's join
// code (for teammates to add themselves with their own role), the list
// of free-text job titles, and a form to add a new one. A job title's
// knowledge base (materials + RAG search) lives on its own detail page.
export default function CompanyDashboardPage() {
  const { user, loading: authLoading } = useRequireAuth();
  const { t } = useLocale();

  const [org, setOrg] = useState<Organization | null>(null);
  const [jobTitles, setJobTitles] = useState<JobTitle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const [newTitle, setNewTitle] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!user) return;
    Promise.all([fetchMyCompany(), fetchJobTitles()])
      .then(([o, jts]) => {
        setOrg(o);
        setJobTitles(jts);
        setError(null);
      })
      .catch((err) =>
        setError(
          err instanceof ApiError ? err.message : t("common.genericError"),
        ),
      )
      .finally(() => setLoading(false));
  }, [user, t]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const title = newTitle.trim();
    if (!title) return;
    setCreating(true);
    try {
      const created = await createJobTitle(
        title,
        newDescription.trim() || undefined,
      );
      setJobTitles((prev) => [created, ...prev]);
      setNewTitle("");
      setNewDescription("");
      setError(null);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : t("company.createError"),
      );
    } finally {
      setCreating(false);
    }
  }

  function copyJoinCode() {
    if (!org) return;
    navigator.clipboard?.writeText(org.joinCode).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

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
          <div className="flex items-center gap-2 font-mono text-xs text-text-muted">
            <Building2 className="h-3.5 w-3.5 text-accent-ink" />
            <span className="font-semibold text-text-primary">
              {t("common.venv")}
            </span>
            <span className="text-border-strong">/</span>
            <span>{t("company.nav")}</span>
            <span className="text-border-strong">/</span>
            <span className="text-[10px] text-text-muted">{org?.name}</span>
          </div>

          <div className="hidden items-center gap-2 border-s border-border ps-4 sm:flex">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            <h1 className="font-mono text-xs font-medium uppercase tracking-wider text-text-primary">
              {org?.name}
            </h1>
          </div>
        </div>

        {/* Global Toolbar */}
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

      {/* Main Viewport Content */}
      <div className="thin-scrollbar overflow-y-auto">
        <div className="mx-auto flex max-w-3xl flex-col gap-8 px-6 py-10">
          {error && (
            <div className="flex items-center gap-2 rounded border border-danger/30 bg-danger/10 p-3 font-mono text-xs text-danger">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* ORGANIZATION SPECIFICATION CARD */}
          <div className="relative rounded border border-border bg-bg-surface p-6 sm:p-7">
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

            <span className="absolute inset-x-0 top-0 h-[2px] bg-accent" />

            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <Building2 className="h-4 w-4 text-accent-ink" />
                <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                  ORGANIZATION_METADATA // ROOT_ADMIN
                </span>
              </div>
              <span className="rounded border border-border bg-bg-base px-2 py-0.5 font-mono text-[10px] text-text-muted">
                {t("company.role")}: {user.companyRole}
              </span>
            </div>

            <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
              <div>
                <h2 className="text-xl font-medium tracking-tight text-text-primary">
                  {org?.name}
                </h2>
                {org?.field && (
                  <p className="mt-1 font-mono text-xs text-text-secondary">
                    SECTOR // {org.field}
                  </p>
                )}
              </div>

              {/* Join Code Chip */}
              <div className="flex flex-col items-start gap-1 sm:items-end">
                <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                  {t("company.joinCodeLabel")}
                </span>
                <button
                  type="button"
                  onClick={copyJoinCode}
                  dir="ltr"
                  className="group inline-flex items-center gap-2 rounded border border-border bg-bg-surface-raised px-3.5 py-1.5 font-mono text-xs font-medium text-text-primary transition-colors hover:border-border-strong"
                >
                  <span className="tracking-wider">{org?.joinCode}</span>
                  {copied ? (
                    <span className="flex items-center gap-1 text-[11px] text-agent-mentor">
                      <Check className="h-3.5 w-3.5" />
                      <span>{t("company.copied")}</span>
                    </span>
                  ) : (
                    <Copy className="h-3.5 w-3.5 text-text-muted transition-colors group-hover:text-text-primary" />
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* NEW JOB TITLE SPECIFICATION FORM */}
          <form
            onSubmit={handleCreate}
            className="relative rounded border border-border bg-bg-surface p-6 sm:p-7"
          >
            <div className="flex items-center justify-between border-b border-border pb-3">
              <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                ROSTER_CONFIGURATION // ADD_POSITION
              </span>
              <span className="font-mono text-[10px] text-text-muted">
                RAG_CONTEXT_READY
              </span>
            </div>

            <div className="mt-4">
              <h2 className="text-base font-medium text-text-primary">
                {t("company.newJobTitleTitle")}
              </h2>
              <p className="mt-1 text-xs leading-relaxed text-text-secondary">
                {t("company.newJobTitleBody")}
              </p>
            </div>

            <div className="mt-5 flex flex-col gap-3.5 border-t border-border/60 pt-4">
              <div className="flex flex-col gap-1.5">
                <label className="font-mono text-[11px] text-text-muted">
                  POSITION_TITLE:
                </label>
                <input
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder={t("company.jobTitlePlaceholder")}
                  className="h-9 rounded border border-border bg-bg-surface-raised px-3 text-xs text-text-primary placeholder:text-text-muted transition-colors focus:border-accent focus:outline-none"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="font-mono text-[11px] text-text-muted">
                  POSITION_DESCRIPTION:
                </label>
                <input
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  placeholder={t("company.jobDescriptionPlaceholder")}
                  className="h-9 rounded border border-border bg-bg-surface-raised px-3 text-xs text-text-primary placeholder:text-text-muted transition-colors focus:border-accent focus:outline-none"
                />
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  disabled={creating || !newTitle.trim()}
                  className="inline-flex h-9 items-center gap-1.5 rounded border border-accent bg-accent px-5 font-mono text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <Plus className="h-3.5 w-3.5" />
                  <span>
                    {creating ? t("common.working") : t("company.addJobTitle")}
                  </span>
                </button>
              </div>
            </div>
          </form>

          {/* JOB TITLES DIRECTORY */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between border-b border-border pb-2">
              <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                {t("company.jobTitlesTitle")}
              </span>
              <span className="font-mono text-[10px] text-text-muted">
                COUNT: {jobTitles.length}
              </span>
            </div>

            {jobTitles.length === 0 ? (
              <div className="rounded border border-dashed border-border bg-bg-surface/50 p-8 text-center font-mono text-xs text-text-muted">
                {t("company.noJobTitles")}
              </div>
            ) : (
              <div className="flex flex-col gap-2.5">
                {jobTitles.map((jt) => (
                  <Link
                    key={jt.id}
                    href={`/company/job-titles/${jt.id}`}
                    className="group relative flex flex-wrap items-center justify-between gap-3 rounded border border-border bg-bg-surface p-4 transition-colors hover:border-border-strong hover:bg-bg-surface-raised"
                  >
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded border border-border bg-bg-base text-accent-ink">
                        <Briefcase className="h-3.5 w-3.5" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="text-xs font-medium text-text-primary group-hover:text-accent-ink transition-colors">
                            {jt.title}
                          </p>
                          <ArrowUpRight className="h-3 w-3 text-text-muted transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                        </div>
                        {jt.description && (
                          <p className="mt-1 text-xs text-text-secondary leading-relaxed">
                            {jt.description}
                          </p>
                        )}
                      </div>
                    </div>

                    <div className="rounded border border-border bg-bg-base/70 px-2.5 py-1 font-mono text-[10px] text-text-muted">
                      {t("company.materialsCount", {
                        count: String(jt.materialCount),
                      })}
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
