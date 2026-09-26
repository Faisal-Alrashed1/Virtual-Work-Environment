"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import type { Week } from "@/lib/projects";
import { useLocale, useRelativeTime } from "@/lib/i18n/locale";

interface WeekStripProps {
  week: Week | null;
  projectTitle: string | null;
}

export function WeekStrip({ week, projectTitle }: WeekStripProps) {
  const { t } = useLocale();
  const { timeUntil } = useRelativeTime();
  if (!week) return null;

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1, duration: 0.4, ease: "easeOut" }}
      className="rounded border border-border bg-bg-surface p-6"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="font-mono text-[11px] text-text-muted">
            {t("weekStrip.weekProject", {
              n: week.weekNumber,
              project: projectTitle ?? t("weekStrip.projectFallback"),
            })}
          </p>
          <h3 className="mt-1 text-lg font-medium text-text-primary">
            {week.bigTaskTitle}
          </h3>
        </div>
        <span className="shrink-0 font-mono text-[11px] text-text-muted">
          {week.status === "completed"
            ? t("weekStrip.complete")
            : t("weekStrip.ends", { time: timeUntil(week.targetEndAt) })}
        </span>
      </div>

      {/* The 5 subtasks as a connected timeline. Done = filled accent,
          up-next = ringed accent, later = hollow. A hairline connector
          runs behind them, blueprint-style. */}
      <ol className="relative mt-6 flex justify-between">
        <span
          className="absolute inset-x-0 top-[7px] h-px bg-border"
          aria-hidden
        />
        {week.subtasksPlan.map((s, i) => {
          const done = i < week.subtasksReleased;
          const upNext = i === week.subtasksReleased && week.status === "active";
          return (
            <li
              key={i}
              className="relative flex min-w-0 flex-1 flex-col items-center px-1 text-center"
            >
              <span
                className="relative z-10 h-3.5 w-3.5 rounded-full border-2 bg-bg-surface"
                style={{
                  borderColor:
                    done || upNext ? "var(--accent)" : "var(--border-strong)",
                  backgroundColor: done ? "var(--accent)" : "var(--bg-surface)",
                }}
              />
              <p
                className={`mt-2 line-clamp-2 text-[11px] leading-tight ${
                  upNext ? "text-text-primary" : "text-text-secondary"
                }`}
              >
                {s.title}
              </p>
              <p className="mt-1 font-mono text-[10px] text-text-muted">
                {done ? t("weekStrip.done") : t("weekStrip.due", { time: timeUntil(s.deadline) })}
              </p>
            </li>
          );
        })}
      </ol>

      <div className="mt-6 flex items-center justify-between">
        <span className="font-mono text-[11px] text-text-muted">
          {t("weekStrip.handedOut", { done: week.subtasksReleased, total: week.subtasksPlan.length })}
        </span>
        <Link
          href="/workspace"
          className="rounded border border-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
        >
          {t("weekStrip.openTaskBoard")}
        </Link>
      </div>
    </motion.section>
  );
}
