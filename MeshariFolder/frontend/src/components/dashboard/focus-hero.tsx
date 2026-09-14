"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import type { Task } from "@/lib/tasks";
import type { Week } from "@/lib/projects";
import { STATUS_LABEL } from "@/lib/tasks";
import { timeUntil } from "@/lib/format";

interface FocusHeroProps {
  /** The task the graduate should act on now: the one open task in the
   * current week (todo/in_progress/submitted). null once the current
   * subtask is reviewed and before the next is released, or before any
   * project exists. */
  task: Task | null;
  week: Week | null;
  hasProject: boolean;
}

const STATUS_HINT: Record<Task["status"], string> = {
  todo: "Ready to start whenever you are.",
  in_progress: "In progress — submit a GitHub link when it's ready for review.",
  submitted: "Submitted — the mentor is reviewing it.",
  reviewed: "Reviewed — nice work.",
};

export function FocusHero({ task, week, hasProject }: FocusHeroProps) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="bg-blueprint-grid relative overflow-hidden rounded border border-border-strong bg-bg-surface p-6 sm:p-8"
    >
      {/* Accent hairline down the left edge — the one signal color, marking
          this as the primary thing on the page (DESIGN.md: accent = the
          manager, who drives the work). */}
      <span className="absolute inset-y-0 left-0 w-[3px] bg-accent" />

      {!hasProject ? (
        <>
          <p className="font-mono text-[11px] text-text-muted">get_started</p>
          <h2 className="mt-2 text-2xl font-medium text-text-primary">
            Your workspace is ready.
          </h2>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-text-secondary">
            Ask your manager for your first task. They&apos;ll set up a
            project calibrated to your background and hand you the first
            piece of it — one focused task at a time.
          </p>
          <Link
            href="/workspace"
            className="mt-5 inline-block rounded border border-accent bg-accent px-5 py-2.5 text-sm font-medium text-accent-text transition-colors hover:bg-accent-strong"
          >
            Ask the manager for a task
          </Link>
        </>
      ) : !task ? (
        <>
          <p className="font-mono text-[11px] text-text-muted">all_clear</p>
          <h2 className="mt-2 text-2xl font-medium text-text-primary">
            You&apos;re all caught up.
          </h2>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-text-secondary">
            Nothing needs your attention right now. Your next task will
            appear here as soon as the manager hands it out.
          </p>
          <Link
            href="/workspace"
            className="mt-5 inline-block rounded border border-border px-5 py-2.5 text-sm text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
          >
            Open the task board
          </Link>
        </>
      ) : (
        <>
          <div className="flex items-center gap-2">
            <p className="font-mono text-[11px] text-text-muted">
              your_focus_now
            </p>
            {week && (
              <span className="font-mono text-[11px] text-text-muted">
                · week {week.weekNumber}
              </span>
            )}
          </div>
          <h2 className="mt-2 text-2xl font-medium leading-snug text-text-primary">
            {task.title}
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-text-secondary">
            {task.description}
          </p>

          <div className="mt-5 flex flex-wrap items-center gap-4">
            <Link
              href="/workspace"
              className="rounded border border-accent bg-accent px-5 py-2.5 text-sm font-medium text-accent-text transition-colors hover:bg-accent-strong"
            >
              {task.status === "todo" ? "Start this task" : "Open on the board"}
            </Link>
            <div className="flex items-center gap-2">
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{ backgroundColor: "var(--agent-manager)" }}
              />
              <span className="text-xs text-text-secondary">
                {STATUS_LABEL[task.status]}
              </span>
            </div>
            {task.deadline && (
              <span className="font-mono text-[11px] text-text-muted">
                due {timeUntil(task.deadline)}
              </span>
            )}
          </div>
          <p className="mt-3 text-xs text-text-muted">{STATUS_HINT[task.status]}</p>
        </>
      )}
    </motion.section>
  );
}
