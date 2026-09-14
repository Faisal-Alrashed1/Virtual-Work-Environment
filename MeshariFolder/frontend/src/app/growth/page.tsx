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
import { AGENTS } from "@/lib/agents";
import { useRequireAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";
import { fetchEmployeeFile, type EmployeeFile } from "@/lib/employee-file";
import { api } from "@/lib/api";
import { averageScore, fetchMyReviews, type Review } from "@/lib/reviews";
import { timeAgo } from "@/lib/format";

const hr = AGENTS.hr;

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
    <div className="rounded border border-border bg-bg-surface-raised px-3 py-2">
      <p className="text-xs text-text-secondary">{item.payload.label}</p>
      <p className="mt-0.5 font-mono text-[11px] text-text-muted">
        {item.value.toFixed(2)} / 5
      </p>
    </div>
  );
}

export default function GrowthPage() {
  const { user, loading: authLoading } = useRequireAuth();

  const [employeeFile, setEmployeeFile] = useState<EmployeeFile | null>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rollingUp, setRollingUp] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [ef, rv] = await Promise.all([fetchEmployeeFile(), fetchMyReviews()]);
      setEmployeeFile(ef);
      setReviews(rv);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load your growth view.");
    } finally {
      setLoading(false);
    }
  }, []);

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
        err instanceof ApiError
          ? err.message
          : "HR couldn't update your file — you may need at least one reviewed task first."
      );
    } finally {
      setRollingUp(false);
    }
  }

  const mentorReviews = reviews.filter((r) => r.agentType === "mentor" && r.taskId);
  const chartData = mentorReviews.map((r) => ({
    label: r.content.slice(0, 24),
    score: Number(averageScore(r).toFixed(2)),
  }));

  if (authLoading || !user) {
    return (
      <main className="flex flex-1 items-center justify-center">
        <p className="text-sm text-text-muted">Loading...</p>
      </main>
    );
  }

  return (
    <main className="min-h-dvh">
      <header className="flex items-center justify-between border-b border-border px-6 py-4">
        <div>
          <Link
            href="/board"
            className="font-mono text-xs text-text-muted hover:text-text-secondary"
          >
            venv / board
          </Link>
          <h1 className="mt-1 text-lg font-medium text-text-primary">Growth</h1>
        </div>
        <button
          type="button"
          onClick={handleAskHr}
          disabled={rollingUp}
          className="rounded border border-accent bg-accent px-4 py-2 text-sm font-medium text-accent-text transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50"
        >
          {rollingUp ? "HR is updating your file..." : "Ask HR for a review"}
        </button>
      </header>

      <div className="mx-auto max-w-2xl px-6 py-8">
        {error && <p className="mb-6 text-sm text-danger">{error}</p>}

        {loading ? (
          <p className="text-sm text-text-muted">Loading...</p>
        ) : (
          <>
            <div className="flex items-center gap-2">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: `var(${hr.colorVar})` }}
              />
              <span className="font-mono text-[11px] text-text-muted">
                employee_file
              </span>
            </div>

            {!employeeFile?.summary ? (
              <p className="mt-5 text-sm text-text-secondary">
                No employee file yet — complete a task and ask HR for a review
                to build one.
              </p>
            ) : (
              <>
                <div className="mt-3 flex flex-wrap gap-2">
                  {employeeFile.skills.map((skill) => (
                    <span
                      key={skill}
                      className="rounded border border-border bg-bg-surface px-2.5 py-1 font-mono text-xs text-text-secondary"
                    >
                      {skill}
                    </span>
                  ))}
                </div>

                <p className="mt-5 text-sm leading-relaxed text-text-secondary">
                  {employeeFile.summary}
                </p>

                <div className="mt-6 grid gap-4 sm:grid-cols-2">
                  <div className="rounded border border-border bg-bg-surface p-4">
                    <p className="font-mono text-[11px] text-text-muted">strengths</p>
                    <ul className="mt-2 flex flex-col gap-2">
                      {employeeFile.strengths.map((item) => (
                        <li key={item} className="flex gap-2 text-sm text-text-secondary">
                          <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-text-muted" />
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="rounded border border-border bg-bg-surface p-4">
                    <p className="font-mono text-[11px] text-text-muted">
                      growth areas
                    </p>
                    <ul className="mt-2 flex flex-col gap-2">
                      {employeeFile.growthAreas.map((item) => (
                        <li key={item} className="flex gap-2 text-sm text-text-secondary">
                          <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-text-muted" />
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </>
            )}

            {mentorReviews.length > 0 && (
              <>
                <p className="mt-10 font-mono text-[11px] text-text-muted">
                  score trend
                </p>
                <div style={{ width: "100%", height: 260 }} className="mt-3">
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
                        tick={{ fill: "var(--text-muted)", fontSize: 11 }}
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
                        tick={{ fill: "var(--text-muted)", fontSize: 11 }}
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

                <p className="mt-10 font-mono text-[11px] text-text-muted">timeline</p>
                <div className="mt-3 flex flex-col gap-3">
                  {mentorReviews.map((review) => (
                    <Link
                      key={review.id}
                      href={`/tasks/${review.taskId}/review`}
                      className="flex items-center justify-between rounded border border-border bg-bg-surface px-4 py-3 transition-colors hover:border-border-strong"
                    >
                      <div>
                        <p className="line-clamp-1 text-sm text-text-primary">
                          {review.content}
                        </p>
                        <p className="mt-0.5 font-mono text-[11px] text-text-muted">
                          {timeAgo(review.createdAt)} ·{" "}
                          {review.verdict === "approved" ? "approved" : "needs changes"}
                        </p>
                      </div>
                      <span className="font-mono text-xs text-text-secondary">
                        {averageScore(review).toFixed(2)}/5
                      </span>
                    </Link>
                  ))}
                </div>
              </>
            )}
          </>
        )}

        <Link
          href="/board"
          className="mt-10 inline-block text-xs text-text-muted hover:text-text-secondary"
        >
          Back to home board
        </Link>
      </div>
    </main>
  );
}
