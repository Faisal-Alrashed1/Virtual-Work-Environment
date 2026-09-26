"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import type { Task } from "@/lib/tasks";
import type { Week } from "@/lib/projects";
import { useLocale, useStatusLabels, useRelativeTime } from "@/lib/i18n/locale";

interface FocusHeroProps {
  /** The task the graduate should act on now: the one open task in the
   * current week (todo/in_progress/submitted). null once the current
   * subtask is reviewed and before the next is released, or before any
   * project exists. */
  task: Task | null;
  week: Week | null;
  hasProject: boolean;
}

export function FocusHero({ task, week, hasProject }: FocusHeroProps) {
  const { t } = useLocale();
  const { timeUntil } = useRelativeTime();
  const statusLabels = useStatusLabels();

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="bg-blueprint-grid relative overflow-hidden rounded border border-border-strong bg-bg-surface p-6 sm:p-8"
    >
      {/* Accent hairline down the leading edge — the one signal color,
          marking this as the primary thing on the page (DESIGN.md:
          accent = the manager, who drives the work). */}
      <span className="absolute inset-y-0 start-0 w-[3px] bg-accent" />

      {!hasProject ? (
        <>
          <p className="font-mono text-[11px] text-text-muted">{t("focusHero.getStartedEyebrow")}</p>
          <h2 className="mt-2 text-2xl font-medium text-text-primary">
            {t("focusHero.workspaceReadyTitle")}
          </h2>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-text-secondary">
            {t("focusHero.workspaceReadyBody")}
          </p>
          <Link
            href="/workspace"
            className="mt-5 inline-block rounded border border-accent bg-accent px-5 py-2.5 text-sm font-medium text-accent-text transition-colors hover:bg-accent-strong"
          >
            {t("focusHero.askManagerCta")}
          </Link>
        </>
      ) : !task ? (
        <>
          <p className="font-mono text-[11px] text-text-muted">{t("focusHero.allClearEyebrow")}</p>
          <h2 className="mt-2 text-2xl font-medium text-text-primary">
            {t("focusHero.allCaughtUpTitle")}
          </h2>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-text-secondary">
            {t("focusHero.allCaughtUpBody")}
          </p>
          <Link
            href="/workspace"
            className="mt-5 inline-block rounded border border-border px-5 py-2.5 text-sm text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
          >
            {t("focusHero.openTaskBoard")}
          </Link>
        </>
      ) : (
        <>
          <div className="flex items-center gap-2">
            <p className="font-mono text-[11px] text-text-muted">
              {t("focusHero.focusNowEyebrow")}
            </p>
            {week && (
              <span className="font-mono text-[11px] text-text-muted">
                {t("focusHero.weekLabel", { n: week.weekNumber })}
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
              {task.status === "todo" ? t("focusHero.startThisTask") : t("focusHero.openOnBoard")}
            </Link>
            <div className="flex items-center gap-2">
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{ backgroundColor: "var(--agent-manager)" }}
              />
              <span className="text-xs text-text-secondary">
                {statusLabels[task.status]}
              </span>
            </div>
            {task.deadline && (
              <span className="font-mono text-[11px] text-text-muted">
                {t("focusHero.due", { time: timeUntil(task.deadline) })}
              </span>
            )}
          </div>
          <p className="mt-3 text-xs text-text-muted">
            {t(`focusHero.statusHint.${task.status}`)}
          </p>
        </>
      )}
    </motion.section>
  );
}
