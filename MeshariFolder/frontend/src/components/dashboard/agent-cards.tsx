"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { AGENTS, AGENT_ORDER, type AgentId } from "@/lib/agents";
import type { Dashboard } from "@/lib/dashboard";
import type { Review } from "@/lib/reviews";
import type { ExtraAgent } from "@/lib/team";
import { timeAgo } from "@/lib/format";

interface AgentCardsProps {
  dashboard: Dashboard;
  reviews: Review[];
  extraAgents: ExtraAgent[];
}

/** A short, live status line per agent, derived from real data — this is
 * what makes the cards feel alive rather than a static "what each agent
 * does" legend. Falls back to a role description before there's activity. */
function agentStatus(
  id: AgentId,
  dashboard: Dashboard,
  reviews: Review[]
): { line: string; meta: string | null } {
  if (id === "manager") {
    if (!dashboard.hasActiveProject)
      return { line: "Waiting to set up your project.", meta: null };
    return {
      line: `${dashboard.tasksTotal} task${dashboard.tasksTotal === 1 ? "" : "s"} assigned so far.`,
      meta: dashboard.weeksTotal > 0 ? `week ${dashboard.weeksTotal} active` : null,
    };
  }
  if (id === "mentor") {
    const taskReviews = reviews.filter((r) => r.kind === "task_review");
    if (taskReviews.length === 0)
      return { line: "No reviews yet — submit a task to get feedback.", meta: null };
    const latest = taskReviews[taskReviews.length - 1];
    return {
      line: `${dashboard.reviewsCount} review${dashboard.reviewsCount === 1 ? "" : "s"} written${
        dashboard.averageScore !== null
          ? `, averaging ${dashboard.averageScore.toFixed(1)}/5`
          : ""
      }.`,
      meta: `last ${timeAgo(latest.createdAt)}`,
    };
  }
  // hr
  const hrTouched = reviews.some(
    (r) => r.agentType === "hr" || r.kind === "behavioral"
  );
  if (!hrTouched)
    return { line: "Will start tracking your growth after your first review.", meta: null };
  return {
    line: `${dashboard.weeksCompleted} week${dashboard.weeksCompleted === 1 ? "" : "s"} evaluated.`,
    meta: "growth view ready",
  };
}

const AGENT_HREF: Record<AgentId, string> = {
  manager: "/meeting",
  mentor: "/meeting",
  hr: "/meeting",
};

export function AgentCards({ dashboard, reviews, extraAgents }: AgentCardsProps) {
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {AGENT_ORDER.map((id, i) => {
        const meta = AGENTS[id];
        const status = agentStatus(id, dashboard, reviews);
        return (
          <motion.div
            key={id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 + 0.05 * i, duration: 0.3, ease: "easeOut" }}
          >
            <Link
              href={AGENT_HREF[id]}
              className="flex h-full flex-col rounded border border-border bg-bg-surface p-4 transition-colors hover:border-border-strong"
            >
              <div className="flex items-center gap-2">
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: `var(${meta.colorVar})` }}
                />
                <span className="font-medium text-text-primary">{meta.name}</span>
                {status.meta && (
                  <span className="ml-auto font-mono text-[10px] text-text-muted">
                    {status.meta}
                  </span>
                )}
              </div>
              <p className="mt-2 text-xs text-text-secondary">{meta.role}</p>
              <p className="mt-3 text-sm leading-relaxed text-text-primary">
                {status.line}
              </p>
            </Link>
          </motion.div>
        );
      })}
      {extraAgents.map((agent, i) => (
        <motion.div
          key={agent.id}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{
            delay: 0.15 + 0.05 * (AGENT_ORDER.length + i),
            duration: 0.3,
            ease: "easeOut",
          }}
          className="flex h-full flex-col rounded border border-dashed border-border p-4"
        >
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-text-muted" />
            <span className="font-medium text-text-primary">{agent.name}</span>
          </div>
          <p className="mt-2 text-xs text-text-secondary">Added during onboarding</p>
          <p className="mt-3 text-sm leading-relaxed text-text-primary">
            {agent.description}
          </p>
        </motion.div>
      ))}
    </div>
  );
}
