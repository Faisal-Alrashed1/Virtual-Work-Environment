"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  ArrowLeft,
  ArrowRight,
  TrendingUp,
  Sparkles,
  RefreshCw,
  Award,
  Compass,
  AlertCircle,
  FileCheck2,
} from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";
import { fetchEmployeeFile, type EmployeeFile } from "@/lib/employee-file";
import { api } from "@/lib/api";
import { averageScore, fetchMyReviews, type Review } from "@/lib/reviews";
import { fetchMyExtraAgents, type ExtraAgent } from "@/lib/team";
import { timeAgo } from "@/lib/format";
import { useAgents, useLocale } from "@/lib/i18n/locale";
import { ThemeToggle } from "@/components/theme-toggle";
import { LocaleToggle } from "@/components/locale-toggle";

interface TooltipPayloadItem {
  value: number;
  payload: { label: string };
}

function ChartTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: TooltipPayloadItem[];
}) {
  if (!active || !payload?.length) return null;
  const item = payload[0];
  return (
    <div className="rounded border border-border bg-bg-surface-raised p-2.5 font-mono shadow-xs">
      <p className="text-xs text-text-primary">{item.payload.label}</p>
      <div className="mt-1 flex items-center gap-1.5 border-t border-border pt-1">
        <span className="h-1.5 w-1.5 rounded-full bg-agent-hr" />
        <p className="text-xs font-semibold text-text-primary">
          {item.value.toFixed(2)}{" "}
          <span className="text-[10px] text-text-muted">/ 5.00</span>
        </p>
      </div>
    </div>
  );
}

export default function GrowthPage() {
  const { user, loading: authLoading } = useRequireAuth();
  const { t, locale } = useLocale();
  const agents = useAgents();
  const { hr } = agents;

  const [employeeFile, setEmployeeFile] = useState<EmployeeFile | null>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [extraAgents, setExtraAgents] = useState<ExtraAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rollingUp, setRollingUp] = useState(false);
  const [checkingIn, setCheckingIn] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [ef, rv, extras] = await Promise.all([
        fetchEmployeeFile(),
        fetchMyReviews(),
        fetchMyExtraAgents(),
      ]);
      setEmployeeFile(ef);
      setReviews(rv);
      setExtraAgents(extras);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("growth.loadError"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    // Fetching on mount is the "subscribe to an external system" case
    // this rule allows; setState only runs after the fetch resolves,
    // not synchronously.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (user) refresh();
  }, [user, refresh]);

  async function handleAskHr() {
    setRollingUp(true);
    setError(null);
    try {
      await api.agents.hrRollup();
      await refresh();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : t("growth.hrRollupError"),
      );
    } finally {
      setRollingUp(false);
    }
  }

  async function handleCareerCheckin() {
    setCheckingIn(true);
    setError(null);
    try {
      await api.agents.careerCoachCheckin();
      await refresh();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : t("growth.careerCheckinError"),
      );
    } finally {
      setCheckingIn(false);
    }
  }

  const hasCareerCoach = extraAgents.some((a) => a.id === "career_coach");
  const mentorReviews = reviews.filter(
    (r) => r.agentType === "mentor" && r.taskId,
  );
  const careerCheckin = reviews
    .filter((r) => r.kind === "career_checkin" && r.careerCheckin)
    .slice(-1)[0];
  const chartData = mentorReviews.map((r) => ({
    label: r.content.slice(0, 24),
    score: Number(averageScore(r).toFixed(2)),
  }));

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

  return (
    <main className="min-h-screen bg-bg-base text-text-primary selection:bg-accent selection:text-accent-text">
      {/* Top Architecture Navigation Bar */}
      <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-border bg-bg-surface/90 px-6 backdrop-blur-md">
        <div className="flex items-center gap-4">
          <Link
            href="/board"
            className="group flex items-center gap-2 font-mono text-xs text-text-muted transition-colors hover:text-text-primary"
          >
            <BackArrow className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5 rtl:group-hover:translate-x-0.5" />
            <span>{t("nav.venvBoard")}</span>
            <span className="text-border-strong">/</span>
            <span className="text-[10px] text-text-muted transition-colors group-hover:text-text-secondary">
              EMPLOYEE_DOSSIER
            </span>
          </Link>

          <div className="hidden items-center gap-2 border-s border-border ps-4 sm:flex">
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ backgroundColor: `var(${hr.colorVar})` }}
            />
            <h1 className="font-mono text-xs font-medium uppercase tracking-wider text-text-primary">
              {t("nav.growthTitle")}
            </h1>
          </div>
        </div>

        {/* Global Action Cluster */}
        <div className="flex items-center gap-2">
          {hasCareerCoach && (
            <button
              type="button"
              onClick={handleCareerCheckin}
              disabled={checkingIn}
              className="inline-flex h-8 items-center gap-1.5 rounded border border-border bg-bg-base px-3 font-mono text-xs text-text-secondary transition-colors hover:border-border-strong hover:bg-bg-surface hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Compass className="h-3.5 w-3.5 text-accent-ink" />
              <span>
                {checkingIn
                  ? t("growth.careerCheckinUpdating")
                  : t("growth.askCareerCheckin")}
              </span>
            </button>
          )}

          <button
            type="button"
            onClick={handleAskHr}
            disabled={rollingUp}
            className="inline-flex h-8 items-center gap-1.5 rounded border border-accent bg-accent px-3.5 font-mono text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw
              className={`h-3 w-3 ${rollingUp ? "animate-spin" : ""}`}
            />
            <span>
              {rollingUp ? t("growth.hrUpdating") : t("growth.askHrReview")}
            </span>
          </button>

          <div className="mx-1 h-4 border-s border-border" />

          <LocaleToggle className="bg-bg-base" />
          <ThemeToggle className="bg-bg-base" />
        </div>
      </header>

      {/* Main Viewport Content */}
      <div className="mx-auto max-w-4xl px-6 py-10">
        {error && (
          <div className="mb-8 flex items-center gap-2 rounded border border-danger/30 bg-danger/10 p-3 font-mono text-xs text-danger">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {loading ? (
          <div className="flex h-64 items-center justify-center">
            <div className="flex items-center gap-2 rounded border border-border bg-bg-surface px-4 py-2 font-mono text-xs text-text-muted">
              <span className="h-1.5 w-1.5 animate-ping rounded-full bg-accent" />
              <span>{t("common.loading")}</span>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-10">
            {/* EMPLOYEE DOSSIER FILE */}
            <div className="relative rounded border border-border bg-bg-surface p-6 sm:p-7">
              {/* Corner tick marks */}
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

              {/* HR identity indicator strip */}
              <span
                className="absolute inset-x-0 top-0 h-[2px]"
                style={{ backgroundColor: `var(${hr.colorVar})` }}
              />

              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
                <div className="flex items-center gap-2">
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ backgroundColor: `var(${hr.colorVar})` }}
                  />
                  <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                    {t("growth.employeeFileEyebrow")}
                  </span>
                </div>
                <span className="font-mono text-[10px] text-text-muted">
                  AGENT // {hr.name}
                </span>
              </div>

              {!employeeFile?.summary ? (
                <div className="py-8 text-center">
                  <p className="text-sm text-text-secondary">
                    {t("growth.noEmployeeFile")}
                  </p>
                </div>
              ) : (
                <div className="mt-5 flex flex-col gap-6">
                  {/* Verified Skills Tags */}
                  {employeeFile.skills.length > 0 && (
                    <div>
                      <span className="block font-mono text-[10px] uppercase text-text-muted">
                        CORE_COMPETENCIES:
                      </span>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {employeeFile.skills.map((skill) => (
                          <span
                            key={skill}
                            className="rounded border border-border bg-bg-surface-raised px-2.5 py-1 font-mono text-xs text-text-primary"
                          >
                            {skill}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Summary Narrative */}
                  <div>
                    <span className="block font-mono text-[10px] uppercase text-text-muted">
                      EVALUATION_SYNTHESIS:
                    </span>
                    <p className="mt-1.5 text-sm leading-relaxed text-text-secondary">
                      {employeeFile.summary}
                    </p>
                  </div>

                  {/* Strengths & Growth Areas Matrix */}
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="rounded border border-border bg-bg-base/60 p-4">
                      <div className="flex items-center gap-1.5 border-b border-border pb-2">
                        <Award className="h-3.5 w-3.5 text-agent-mentor" />
                        <span className="font-mono text-[10px] uppercase tracking-wider text-text-primary">
                          {t("growth.strengths")}
                        </span>
                      </div>
                      <ul className="mt-3 flex flex-col gap-2">
                        {employeeFile.strengths.map((item) => (
                          <li
                            key={item}
                            className="flex items-start gap-2 text-xs text-text-secondary leading-relaxed"
                          >
                            <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-agent-mentor" />
                            <span>{item}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div className="rounded border border-border bg-bg-base/60 p-4">
                      <div className="flex items-center gap-1.5 border-b border-border pb-2">
                        <TrendingUp className="h-3.5 w-3.5 text-accent-ink" />
                        <span className="font-mono text-[10px] uppercase tracking-wider text-text-primary">
                          {t("growth.growthAreas")}
                        </span>
                      </div>
                      <ul className="mt-3 flex flex-col gap-2">
                        {employeeFile.growthAreas.map((item) => (
                          <li
                            key={item}
                            className="flex items-start gap-2 text-xs text-text-secondary leading-relaxed"
                          >
                            <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-accent" />
                            <span>{item}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* CAREER COACH REPORT (OPTIONAL ROSTER ACTION) */}
            {careerCheckin?.careerCheckin && (
              <div className="relative rounded border border-border bg-bg-surface p-6">
                <span className="absolute inset-x-0 top-0 h-[2px] bg-accent" />
                <div className="flex items-center justify-between border-b border-border pb-3">
                  <div className="flex items-center gap-2">
                    <Sparkles className="h-3.5 w-3.5 text-accent-ink" />
                    <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                      {t("growth.careerCheckinEyebrow")}
                    </span>
                  </div>
                  <span className="font-mono text-[10px] text-text-muted">
                    REVIEW_ID // {careerCheckin.id.slice(0, 8)}
                  </span>
                </div>

                <p className="mt-4 text-xs leading-relaxed text-text-secondary">
                  {careerCheckin.content}
                </p>

                <div className="mt-5 border-t border-border/60 pt-4">
                  <span className="block font-mono text-[10px] uppercase tracking-wider text-text-muted">
                    {t("growth.resumeHighlights")}
                  </span>
                  <ul className="mt-2.5 flex flex-col gap-2">
                    {careerCheckin.careerCheckin.resumeHighlights.map(
                      (item) => (
                        <li
                          key={item}
                          className="flex items-start gap-2 text-xs text-text-secondary leading-relaxed"
                        >
                          <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-accent" />
                          <span>{item}</span>
                        </li>
                      ),
                    )}
                  </ul>
                </div>

                <div className="mt-4 rounded border border-border bg-bg-base/70 p-3 font-mono text-xs">
                  <span className="text-text-muted">
                    {t("growth.suggestedFocus")}:{" "}
                  </span>
                  <span className="text-text-primary">
                    {careerCheckin.careerCheckin.suggestedFocus}
                  </span>
                </div>
              </div>
            )}

            {/* PERFORMANCE TRAJECTORY CHART */}
            {mentorReviews.length > 0 && (
              <div className="relative rounded border border-border bg-bg-surface p-6">
                <div className="flex items-center justify-between border-b border-border pb-3">
                  <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                    {t("growth.scoreTrend")}
                  </span>
                  <span className="font-mono text-[10px] text-text-muted">
                    DATA_POINTS: {chartData.length}
                  </span>
                </div>

                <div style={{ width: "100%", height: 260 }} className="mt-6">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart
                      data={chartData}
                      margin={{ top: 8, right: 8, bottom: 40, left: 8 }}
                    >
                      <CartesianGrid
                        stroke="var(--line-grid)"
                        strokeDasharray="3 3"
                        vertical={false}
                      />
                      <XAxis
                        dataKey="label"
                        tick={{
                          fill: "var(--text-muted)",
                          fontSize: 10,
                          fontFamily: "var(--font-mono)",
                        }}
                        axisLine={{ stroke: "var(--border)" }}
                        tickLine={false}
                        angle={-15}
                        textAnchor="end"
                        height={60}
                        interval={0}
                      />
                      <YAxis
                        domain={[0, 5]}
                        ticks={[0, 1, 2, 3, 4, 5]}
                        tick={{
                          fill: "var(--text-muted)",
                          fontSize: 10,
                          fontFamily: "var(--font-mono)",
                        }}
                        axisLine={{ stroke: "var(--border)" }}
                        tickLine={false}
                        width={24}
                      />
                      <Tooltip content={<ChartTooltip />} />
                      <Line
                        type="monotone"
                        dataKey="score"
                        stroke="var(--agent-hr)"
                        strokeWidth={2}
                        dot={{ r: 4, fill: "var(--agent-hr)", strokeWidth: 0 }}
                        activeDot={{ r: 6 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* TIMELINE RECORDS */}
            {mentorReviews.length > 0 && (
              <div className="relative rounded border border-border bg-bg-surface p-6">
                <div className="flex items-center justify-between border-b border-border pb-3">
                  <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                    {t("growth.timeline")}
                  </span>
                  <span className="font-mono text-[10px] text-text-muted">
                    LOG_COUNT: {mentorReviews.length}
                  </span>
                </div>

                <div className="mt-4 flex flex-col gap-2.5">
                  {mentorReviews.map((review) => (
                    <Link
                      key={review.id}
                      href={`/tasks/${review.taskId}/review`}
                      className="group flex flex-wrap items-center justify-between gap-3 rounded border border-border bg-bg-base/50 p-3.5 transition-colors hover:border-border-strong hover:bg-bg-surface-raised"
                    >
                      <div className="flex items-start gap-3">
                        <FileCheck2 className="mt-0.5 h-4 w-4 shrink-0 text-text-muted group-hover:text-text-primary transition-colors" />
                        <div>
                          <p className="line-clamp-1 text-xs font-medium text-text-primary">
                            {review.content}
                          </p>
                          <p className="mt-1 font-mono text-[10px] text-text-muted">
                            {timeAgo(review.createdAt)} ·{" "}
                            <span
                              className={
                                review.verdict === "approved"
                                  ? "text-agent-mentor"
                                  : "text-danger"
                              }
                            >
                              {review.verdict === "approved"
                                ? t("growth.approved")
                                : t("growth.needsChanges")}
                            </span>
                          </p>
                        </div>
                      </div>

                      <div className="rounded border border-border bg-bg-surface px-2.5 py-1 font-mono text-xs font-semibold text-text-primary">
                        {averageScore(review).toFixed(2)}
                        <span className="text-[10px] font-normal text-text-muted">
                          {" "}
                          / 5
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
              </div>
            )}

            {/* Back link */}
            <div className="border-t border-border pt-4">
              <Link
                href="/board"
                className="group inline-flex items-center gap-1.5 font-mono text-xs text-text-muted transition-colors hover:text-text-primary"
              >
                <BackArrow className="h-3 w-3 transition-transform group-hover:-translate-x-0.5 rtl:group-hover:translate-x-0.5" />
                <span>{t("growth.backToBoard")}</span>
              </Link>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
