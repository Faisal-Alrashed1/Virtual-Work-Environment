"use client";

import { AnimatePresence, motion } from "framer-motion";
import Link from "next/link";
import type { AgentId } from "@/lib/agents";
import type { ExtraAgent } from "@/lib/team";
import type { Week } from "@/lib/projects";
import { useAgents, useLocale, useRelativeTime } from "@/lib/i18n/locale";

// Reserved sentinels are "employee-file" and "week"; anything else is
// either one of the three default agent ids or an extra agent's catalog
// id (looked up against extraAgents below — there's no separate literal
// type for those since the catalog can grow).
export type BoardSelection = string | null;

interface DetailPanelProps {
  selection: BoardSelection;
  hasCv: boolean;
  /** The graduate's own most recently reviewed task, if any — powers the
   * mentor card's example link. null until they actually have one. */
  reviewedTaskId: string | null;
  /** The active Week, for the "week" selection — null while it's still
   * loading or before the graduate has one yet. */
  week: Week | null;
  projectTitle: string | null;
  /** Optional agents the graduate added during onboarding — looked up
   * here when the selection isn't one of the three default agent ids. */
  extraAgents: ExtraAgent[];
  onClose: () => void;
}

export function DetailPanel({
  selection,
  hasCv,
  reviewedTaskId,
  week,
  projectTitle,
  extraAgents,
  onClose,
}: DetailPanelProps) {
  const { t, dir } = useLocale();
  const { timeUntil } = useRelativeTime();
  const agents = useAgents();
  // framer-motion's x transform is a physical offset (translateX), not
  // direction-aware like the `end-0` position below — so the slide-in
  // origin has to be flipped explicitly, or the panel would animate in
  // from the physical right even once RTL has moved it to the left edge.
  const offscreenX = dir === "rtl" ? "-100%" : "100%";

  const NEXT_UP: Partial<Record<AgentId, string>> = {
    manager: t("detailPanel.nextUpManager"),
    hr: t("detailPanel.nextUpHr"),
  };
  const BOX_LABEL: Record<AgentId, string> = {
    manager: t("detailPanel.boxLabelManager"),
    mentor: t("detailPanel.boxLabelMentor"),
    hr: t("detailPanel.boxLabelHr"),
  };
  const AGENT_LINK: Partial<Record<AgentId, { href: string; label: string }>> = {
    manager: { href: "/tasks", label: t("detailPanel.openTaskBoard") },
    hr: { href: "/growth", label: t("detailPanel.openGrowthView") },
  };

  const isReserved = selection === "employee-file" || selection === "week";
  const isDefaultAgent = !isReserved && selection !== null && selection in agents;
  const meta = isDefaultAgent ? agents[selection as AgentId] : null;
  const customAgent =
    !isReserved && !isDefaultAgent && selection
      ? (extraAgents.find((a) => a.id === selection) ?? null)
      : null;
  // Mentor is the one card whose link depends on real data: point at the
  // graduate's own reviewed task once they have one, otherwise fall back
  // to the task board rather than link to a demo task that doesn't exist.
  const agentLink =
    meta?.id === "mentor"
      ? reviewedTaskId
        ? { href: `/tasks/${reviewedTaskId}/review`, label: t("detailPanel.seeYourReview") }
        : { href: "/tasks", label: t("detailPanel.openTaskBoard") }
      : meta
        ? AGENT_LINK[meta.id]
        : undefined;
  const nextUpText =
    meta?.id === "mentor"
      ? reviewedTaskId
        ? t("detailPanel.mentorNextUpWithReview")
        : t("detailPanel.mentorNextUpNoReview")
      : meta
        ? NEXT_UP[meta.id]
        : undefined;

  return (
    <AnimatePresence>
      {selection && (
        <>
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/40"
          />
          <motion.aside
            key="panel"
            initial={{ x: offscreenX }}
            animate={{ x: 0 }}
            exit={{ x: offscreenX }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className="fixed inset-y-0 end-0 z-50 flex w-full max-w-sm flex-col border-s border-border bg-bg-surface-raised p-6"
          >
            {/* Content scrolls internally if it doesn't fit — the page
                itself never does, however much the "week" detail grows. */}
            <div className="min-h-0 flex-1 overflow-y-auto">
              {meta ? (
                <>
                  <div className="flex items-center gap-2">
                    <span
                      className="h-2.5 w-2.5 rounded-full"
                      style={{ backgroundColor: `var(${meta.colorVar})` }}
                    />
                    <h2 className="text-lg font-medium text-text-primary">
                      {meta.name}
                    </h2>
                  </div>
                  <p className="mt-1 text-sm text-text-secondary">
                    {meta.role}
                  </p>
                  <p className="mt-5 text-sm leading-relaxed text-text-secondary">
                    {meta.description}
                  </p>
                  <div className="mt-8 rounded border border-border bg-bg-surface px-4 py-3">
                    <p className="font-mono text-xs text-text-muted">
                      {BOX_LABEL[meta.id]}
                    </p>
                    <p className="mt-1 text-sm text-text-secondary">
                      {nextUpText}
                    </p>
                    {agentLink && (
                      <Link
                        href={agentLink.href}
                        className="mt-3 inline-block rounded border border-accent bg-accent px-3 py-1.5 text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong"
                      >
                        {agentLink.label}
                      </Link>
                    )}
                  </div>
                </>
              ) : customAgent ? (
                <>
                  <div className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full bg-text-muted" />
                    <h2 className="text-lg font-medium text-text-primary">
                      {customAgent.name}
                    </h2>
                  </div>
                  <p className="mt-1 text-sm text-text-secondary">
                    {t("detailPanel.addedToTeam")}
                  </p>
                  <p className="mt-5 text-sm leading-relaxed text-text-secondary">
                    {customAgent.description}
                  </p>
                  <div className="mt-8 rounded border border-dashed border-border bg-bg-surface px-4 py-3">
                    <p className="font-mono text-xs text-text-muted">{t("detailPanel.statusLabel")}</p>
                    <p className="mt-1 text-sm text-text-secondary">
                      {t("detailPanel.customAgentStatus")}
                    </p>
                  </div>
                </>
              ) : selection === "week" ? (
                <>
                  <div className="flex items-center gap-2">
                    <span
                      className="h-2.5 w-2.5 rounded-full"
                      style={{ backgroundColor: "var(--agent-manager)" }}
                    />
                    <h2 className="text-lg font-medium text-text-primary">
                      {week ? t("detailPanel.weekTitle", { n: week.weekNumber }) : t("detailPanel.weekStatusFallback")}
                    </h2>
                  </div>
                  {projectTitle && (
                    <p className="mt-1 text-sm text-text-secondary">
                      {projectTitle}
                    </p>
                  )}
                  {!week ? (
                    <p className="mt-5 text-sm leading-relaxed text-text-secondary">
                      {t("detailPanel.noActiveWeek")}
                    </p>
                  ) : (
                    <>
                      <p className="mt-5 text-sm leading-relaxed text-text-secondary">
                        {week.bigTaskDescription}
                      </p>
                      <div className="mt-6 flex items-center justify-between">
                        <p className="font-mono text-[11px] text-text-muted">
                          {t("detailPanel.handedOut", { done: week.subtasksReleased, total: week.subtasksPlan.length })}
                        </p>
                        <p className="font-mono text-[11px] text-text-muted">
                          {week.status === "completed"
                            ? t("detailPanel.weekComplete")
                            : t("detailPanel.ends", { time: timeUntil(week.targetEndAt) })}
                        </p>
                      </div>
                      <ul className="mt-4 flex flex-col gap-2">
                        {week.subtasksPlan.map((s, i) => {
                          const done = i < week.subtasksReleased;
                          const upNext = i === week.subtasksReleased;
                          return (
                            <li
                              key={i}
                              className={`rounded border bg-bg-surface px-3 py-2 ${
                                upNext ? "border-accent" : "border-border"
                              }`}
                            >
                              <div className="flex items-center justify-between gap-2">
                                <p className="line-clamp-1 text-sm text-text-primary">
                                  {s.title}
                                </p>
                                <span className="shrink-0 font-mono text-[10px] text-text-muted">
                                  {done ? t("detailPanel.done") : upNext ? t("detailPanel.upNext") : t("detailPanel.later")}
                                </span>
                              </div>
                              <p className="mt-1 font-mono text-[11px] text-text-muted">
                                {t("detailPanel.due", { time: timeUntil(s.deadline) })}
                              </p>
                            </li>
                          );
                        })}
                      </ul>
                      <Link
                        href="/workspace"
                        className="mt-6 inline-block rounded border border-accent bg-accent px-3 py-1.5 text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong"
                      >
                        {t("detailPanel.openTaskBoard")}
                      </Link>
                    </>
                  )}
                </>
              ) : (
                <>
                  <h2 className="text-lg font-medium text-text-primary">
                    {t("detailPanel.employeeFileTitle")}
                  </h2>
                  <p className="mt-1 text-sm text-text-secondary">
                    {t("detailPanel.employeeFileSubtitle")}
                  </p>
                  <p className="mt-5 text-sm leading-relaxed text-text-secondary">
                    {t("detailPanel.employeeFileBody")}
                  </p>
                  <div className="mt-8 rounded border border-border bg-bg-surface px-4 py-3">
                    <p className="font-mono text-xs text-text-muted">
                      {t("detailPanel.growthViewLabel")}
                    </p>
                    <p className="mt-1 text-sm text-text-secondary">
                      {t("detailPanel.growthViewBody")}
                    </p>
                    <Link
                      href="/growth"
                      className="mt-3 inline-block rounded border border-accent bg-accent px-3 py-1.5 text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong"
                    >
                      {t("detailPanel.openGrowthView")}
                    </Link>
                  </div>
                  <div className="mt-3 rounded border border-border bg-bg-surface px-4 py-3">
                    <p className="font-mono text-xs text-text-muted">{t("detailPanel.cvLabel")}</p>
                    <p className="mt-1 text-sm text-text-secondary">
                      {hasCv ? t("detailPanel.cvOnFile") : t("detailPanel.cvNotOnFile")}
                    </p>
                    <Link
                      href="/onboarding/cv"
                      className="mt-3 inline-block rounded border border-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
                    >
                      {hasCv ? t("detailPanel.updateCv") : t("detailPanel.addCv")}
                    </Link>
                  </div>
                </>
              )}
            </div>
            <button
              type="button"
              onClick={onClose}
              className="mt-4 self-start rounded border border-border px-4 py-2 text-sm text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
            >
              {t("common.close")}
            </button>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
