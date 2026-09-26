"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  GitBranch,
  CheckCircle2,
  AlertTriangle,
  FileText,
} from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";
import { fetchTaskDetail, type Task } from "@/lib/tasks";
import { fetchTaskReview, type Review } from "@/lib/reviews";
import { RubricBar } from "@/components/rubric-bar";
import { AttachmentList } from "@/components/workspace/attachment-list";
import { useAgents, useLocale } from "@/lib/i18n/locale";
import { ThemeToggle } from "@/components/theme-toggle";
import { LocaleToggle } from "@/components/locale-toggle";

interface ReviewPageProps {
  params: Promise<{ id: string }>;
}

export default function ReviewPage({ params }: ReviewPageProps) {
  const { id } = use(params);
  const { user, loading: authLoading } = useRequireAuth();
  const { t, locale } = useLocale();
  const { mentor } = useAgents();

  const [task, setTask] = useState<Task | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    Promise.all([fetchTaskDetail(id), fetchTaskReview(id)])
      .then(([t, r]) => {
        setTask(t);
        setReview(r);
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : t("review.loadError")),
      )
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, user]);

  const BackArrow = locale === "ar" ? ArrowRight : ArrowLeft;

  if (authLoading || !user) {
    return (
      <main className="flex min-h-screen flex-1 items-center justify-center bg-bg-base text-text-primary">
        <div className="flex items-center gap-2 rounded border border-border bg-bg-surface px-4 py-3 font-mono text-xs text-text-muted">
          <span className="h-2 w-2 animate-ping rounded-full bg-accent" />
          <span>{t("common.loading")}</span>
        </div>
      </main>
    );
  }

  const isApproved = review?.verdict === "approved";

  return (
    <main className="min-h-screen bg-bg-base text-text-primary selection:bg-accent selection:text-accent-text">
      {/* Top Architecture Navigation Bar */}
      <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-border bg-bg-surface/90 px-6 backdrop-blur-md">
        <div className="flex items-center gap-4">
          <Link
            href="/workspace"
            className="group flex items-center gap-2 font-mono text-xs text-text-muted transition-colors hover:text-text-primary"
          >
            <BackArrow className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5 rtl:group-hover:translate-x-0.5" />
            <span>{t("nav.venvWorkspace")}</span>
            <span className="text-border-strong">/</span>
            <span className="text-[10px] text-text-muted transition-colors group-hover:text-text-secondary">
              AUDIT_REPORT
            </span>
          </Link>

          <div className="hidden items-center gap-2 border-s border-border ps-4 sm:flex">
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ backgroundColor: `var(${mentor.colorVar})` }}
            />
            <h1 className="font-mono text-xs font-medium uppercase tracking-wider text-text-primary">
              {t("nav.mentorReviewTitle")}
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <LocaleToggle className="bg-bg-base" />
          <ThemeToggle className="bg-bg-base" />
        </div>
      </header>

      {/* Main Review Viewport */}
      <div className="mx-auto max-w-3xl px-6 py-10">
        {loading ? (
          <div className="flex h-64 items-center justify-center">
            <div className="flex items-center gap-2 rounded border border-border bg-bg-surface px-4 py-2 font-mono text-xs text-text-muted">
              <span className="h-1.5 w-1.5 animate-ping rounded-full bg-accent" />
              <span>{t("common.loading")}</span>
            </div>
          </div>
        ) : error ? (
          <div className="rounded border border-danger/30 bg-danger/10 p-4 font-mono text-xs text-danger">
            {error}
          </div>
        ) : !task ? (
          <div className="rounded border border-border bg-bg-surface p-8 text-center">
            <p className="text-sm text-text-secondary">
              {t("review.taskNotFound")}
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-8">
            {/* SUBMISSION SPECIFICATION CARD */}
            <div className="relative rounded border border-border bg-bg-surface p-6">
              {/* Corner marks */}
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

              <div className="flex items-center justify-between border-b border-border pb-3">
                <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                  {t("review.taskLabel")} {task.id.slice(0, 8)}
                </span>
                <span className="font-mono text-[10px] text-text-muted">
                  STATUS: {task.status.toUpperCase()}
                </span>
              </div>

              <h2 className="mt-3 text-lg font-medium text-text-primary">
                {task.title}
              </h2>

              {task.githubLink && (
                <div className="mt-3 flex items-center gap-2 rounded border border-border bg-bg-base/70 px-3 py-1.5 font-mono text-xs text-text-secondary">
                  <GitBranch className="h-3.5 w-3.5 text-accent-ink shrink-0" />
                  <span
                    dir="ltr"
                    className="truncate text-text-muted hover:text-text-primary transition-colors"
                  >
                    {task.githubLink}
                  </span>
                </div>
              )}

              {task.submissionText && (
                <div className="mt-4 rounded border border-border/60 bg-bg-base/40 p-3.5">
                  <span className="block font-mono text-[10px] uppercase text-text-muted">
                    SUBMISSION_NOTES:
                  </span>
                  <p className="mt-1 whitespace-pre-line text-xs leading-relaxed text-text-secondary">
                    {task.submissionText}
                  </p>
                </div>
              )}

              <div className="mt-4">
                <AttachmentList
                  taskId={task.id}
                  attachments={task.attachments}
                />
              </div>
            </div>

            {/* MENTOR EVALUATION REPORT */}
            {!review ? (
              <div className="rounded border border-dashed border-border bg-bg-surface/50 p-8 text-center">
                <FileText className="mx-auto h-6 w-6 text-text-muted" />
                <p className="mt-2 text-sm text-text-secondary">
                  {t("review.noReviewYet")}
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-6">
                {/* VERDICT BADGE & SUMMARY */}
                <div
                  className="relative rounded border p-6 bg-bg-surface"
                  style={{
                    borderColor: isApproved
                      ? "var(--agent-mentor)"
                      : "color-mix(in srgb, var(--danger) 40%, transparent)",
                  }}
                >
                  <span
                    className="absolute inset-x-0 top-0 h-[2px]"
                    style={{
                      backgroundColor: isApproved
                        ? "var(--agent-mentor)"
                        : "var(--danger)",
                    }}
                  />

                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
                    <div className="flex items-center gap-2.5">
                      {isApproved ? (
                        <CheckCircle2
                          className="h-5 w-5 text-agent-mentor"
                          strokeWidth={2}
                        />
                      ) : (
                        <AlertTriangle
                          className="h-5 w-5 text-danger"
                          strokeWidth={2}
                        />
                      )}
                      <div>
                        <h3 className="font-mono text-sm font-semibold tracking-wide text-text-primary uppercase">
                          {isApproved
                            ? t("review.approved")
                            : t("review.needsChanges")}
                        </h3>
                        <p className="font-mono text-[10px] text-text-muted">
                          {t("review.by", { name: mentor.name })} {mentor.role}
                        </p>
                      </div>
                    </div>

                    <span className="font-mono text-[10px] rounded border border-border bg-bg-base px-2 py-0.5 text-text-muted">
                      RUBRIC_V2 // VERDICT_RECORDED
                    </span>
                  </div>

                  <p className="mt-4 text-sm leading-relaxed text-text-secondary">
                    {review.content}
                  </p>
                </div>

                {/* RUBRIC SCORING BREAKDOWN */}
                <div className="relative rounded border border-border bg-bg-surface p-6">
                  <div className="flex items-center justify-between border-b border-border pb-3">
                    <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                      EVALUATION_CRITERIA // 1-5_SCALE
                    </span>
                    <span className="font-mono text-[10px] text-text-muted">
                      APPROVAL_BAR: 3.0
                    </span>
                  </div>

                  <div className="mt-5 flex flex-col gap-4">
                    {review.categories.map((category) => (
                      <RubricBar
                        key={category.key}
                        label={category.label}
                        score={category.score}
                      />
                    ))}
                  </div>
                </div>

                {/* ITEMISED FEEDBACK & ACTION POINTS */}
                {review.comments.length > 0 && (
                  <div className="relative rounded border border-border bg-bg-surface p-6">
                    <div className="flex items-center justify-between border-b border-border pb-3">
                      <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                        {t("review.commentsLabel")}
                      </span>
                      <span className="font-mono text-[10px] text-text-muted">
                        COUNT: {review.comments.length}
                      </span>
                    </div>

                    <div className="mt-4 flex flex-col gap-3">
                      {review.comments.map((comment) => {
                        const categoryLabel =
                          review.categories.find(
                            (c) => c.key === comment.category,
                          )?.label ?? comment.category;
                        return (
                          <div
                            key={comment.id}
                            className="rounded border border-border bg-bg-surface-raised p-4 border-s-2 border-s-accent"
                          >
                            <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                              [{categoryLabel}]
                            </span>
                            <p className="mt-1.5 text-xs leading-relaxed text-text-secondary">
                              {comment.content}
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Back to Workspace Footer Link */}
            <div className="border-t border-border pt-6">
              <Link
                href="/workspace"
                className="group inline-flex items-center gap-1.5 font-mono text-xs text-text-muted transition-colors hover:text-text-primary"
              >
                <BackArrow className="h-3 w-3 transition-transform group-hover:-translate-x-0.5 rtl:group-hover:translate-x-0.5" />
                <span>{t("review.backToTaskBoard")}</span>
              </Link>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
