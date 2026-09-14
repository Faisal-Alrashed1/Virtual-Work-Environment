"use client";

import { AnimatePresence, motion } from "framer-motion";
import Link from "next/link";
import { AGENTS, type AgentId } from "@/lib/agents";
import type { ExtraAgent } from "@/lib/team";
import type { Week } from "@/lib/projects";
import { timeUntil } from "@/lib/format";

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

const NEXT_UP: Partial<Record<AgentId, string>> = {
  manager: "The task board is live — see and act on what the manager assigns.",
  hr: "The growth view is live — a score trend and timeline across reviews.",
};

const BOX_LABEL: Record<AgentId, string> = {
  manager: "task board",
  mentor: "example review",
  hr: "growth view",
};

const AGENT_LINK: Partial<Record<AgentId, { href: string; label: string }>> = {
  manager: { href: "/tasks", label: "Open task board" },
  hr: { href: "/growth", label: "Open growth view" },
};

export function DetailPanel({
  selection,
  hasCv,
  reviewedTaskId,
  week,
  projectTitle,
  extraAgents,
  onClose,
}: DetailPanelProps) {
  const isReserved = selection === "employee-file" || selection === "week";
  const isDefaultAgent = !isReserved && selection !== null && selection in AGENTS;
  const meta = isDefaultAgent ? AGENTS[selection as AgentId] : null;
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
        ? { href: `/tasks/${reviewedTaskId}/review`, label: "See your review" }
        : { href: "/tasks", label: "Open task board" }
      : meta
        ? AGENT_LINK[meta.id]
        : undefined;
  const nextUpText =
    meta?.id === "mentor"
      ? reviewedTaskId
        ? "See a worked example: feedback plus a rubric score on your own submitted task."
        : "Submit a task first — the mentor reviews it with feedback and a rubric score."
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
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className="fixed inset-y-0 right-0 z-50 flex w-full max-w-sm flex-col border-l border-border bg-bg-surface-raised p-6"
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
                    Added to your team during onboarding
                  </p>
                  <p className="mt-5 text-sm leading-relaxed text-text-secondary">
                    {customAgent.description}
                  </p>
                  <div className="mt-8 rounded border border-dashed border-border bg-bg-surface px-4 py-3">
                    <p className="font-mono text-xs text-text-muted">status</p>
                    <p className="mt-1 text-sm text-text-secondary">
                      Not wired into the task flow yet — Manager, Mentor, and HR do the
                      actual reviewing for now.
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
                      {week ? `Week ${week.weekNumber}` : "Week status"}
                    </h2>
                  </div>
                  {projectTitle && (
                    <p className="mt-1 text-sm text-text-secondary">
                      {projectTitle}
                    </p>
                  )}
                  {!week ? (
                    <p className="mt-5 text-sm leading-relaxed text-text-secondary">
                      No active week yet — ask the manager for your first task
                      and one will start.
                    </p>
                  ) : (
                    <>
                      <p className="mt-5 text-sm leading-relaxed text-text-secondary">
                        {week.bigTaskDescription}
                      </p>
                      <div className="mt-6 flex items-center justify-between">
                        <p className="font-mono text-[11px] text-text-muted">
                          {week.subtasksReleased}/{week.subtasksPlan.length}{" "}
                          handed out
                        </p>
                        <p className="font-mono text-[11px] text-text-muted">
                          {week.status === "completed"
                            ? "week complete"
                            : `ends ${timeUntil(week.targetEndAt)}`}
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
                                  {done ? "done" : upNext ? "up next" : "later"}
                                </span>
                              </div>
                              <p className="mt-1 font-mono text-[11px] text-text-muted">
                                due {timeUntil(s.deadline)}
                              </p>
                            </li>
                          );
                        })}
                      </ul>
                      <Link
                        href="/workspace"
                        className="mt-6 inline-block rounded border border-accent bg-accent px-3 py-1.5 text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong"
                      >
                        Open task board
                      </Link>
                    </>
                  )}
                </>
              ) : (
                <>
                  <h2 className="text-lg font-medium text-text-primary">
                    Employee file
                  </h2>
                  <p className="mt-1 text-sm text-text-secondary">
                    The one record all three agents read from and write to.
                  </p>
                  <p className="mt-5 text-sm leading-relaxed text-text-secondary">
                    Your CV, skills, task history, and every review live here.
                    When the mentor reviews your code, HR sees it. When HR notes
                    a growth area, the manager&apos;s next task can account for
                    it — no agent works from a stale or partial picture of you.
                  </p>
                  <div className="mt-8 rounded border border-border bg-bg-surface px-4 py-3">
                    <p className="font-mono text-xs text-text-muted">
                      growth view
                    </p>
                    <p className="mt-1 text-sm text-text-secondary">
                      Skills, strengths, growth areas, and the score trend
                      behind them — HR&apos;s view of this same file.
                    </p>
                    <Link
                      href="/growth"
                      className="mt-3 inline-block rounded border border-accent bg-accent px-3 py-1.5 text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong"
                    >
                      Open growth view
                    </Link>
                  </div>
                  <div className="mt-3 rounded border border-border bg-bg-surface px-4 py-3">
                    <p className="font-mono text-xs text-text-muted">cv</p>
                    <p className="mt-1 text-sm text-text-secondary">
                      {hasCv
                        ? "On file — the manager uses it to calibrate your tasks."
                        : "Not on file yet — the manager is working from your task history alone."}
                    </p>
                    <Link
                      href="/onboarding/cv"
                      className="mt-3 inline-block rounded border border-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
                    >
                      {hasCv ? "Update your CV" : "Add your CV"}
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
              Close
            </button>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
