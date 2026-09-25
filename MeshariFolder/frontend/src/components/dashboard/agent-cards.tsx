"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { AGENT_ORDER, type AgentId, type AgentMeta } from "@/lib/agents";
import type { Dashboard } from "@/lib/dashboard";
import type { Review } from "@/lib/reviews";
import type { ExtraAgent } from "@/lib/team";
import { useAgents, useLocale, useRelativeTime } from "@/lib/i18n/locale";

interface AgentCardsProps {
  dashboard: Dashboard;
  reviews: Review[];
  extraAgents: ExtraAgent[];
}

/** A short, live status line per agent, derived from real data — this is
 * what makes the cards feel alive rather than a static "what each agent
 * does" legend. Falls back to a role description before there's activity. */
function useAgentStatus(
  id: AgentId,
  dashboard: Dashboard,
  reviews: Review[]
): { line: string; meta: string | null } {
  const { t, tPlural } = useLocale();
  const { timeAgo } = useRelativeTime();
  if (id === "manager") {
    if (!dashboard.hasActiveProject)
      return { line: t("agentCards.waitingSetup"), meta: null };
    return {
      line: tPlural("agentCards.tasksAssigned", dashboard.tasksTotal, { n: dashboard.tasksTotal }),
      meta: dashboard.weeksTotal > 0 ? t("agentCards.weekActive", { n: dashboard.weeksTotal }) : null,
    };
  }
  if (id === "mentor") {
    const taskReviews = reviews.filter((r) => r.kind === "task_review");
    if (taskReviews.length === 0)
      return { line: t("agentCards.noReviewsSubmit"), meta: null };
    const latest = taskReviews[taskReviews.length - 1];
    const avgSuffix =
      dashboard.averageScore !== null
        ? t("agentCards.averaging", { score: dashboard.averageScore.toFixed(1) })
        : "";
    return {
      line: tPlural("agentCards.reviewsWritten", dashboard.reviewsCount, {
        n: dashboard.reviewsCount,
        avg: avgSuffix,
      }),
      meta: t("agentCards.lastTime", { time: timeAgo(latest.createdAt) }),
    };
  }
  // hr
  const hrTouched = reviews.some(
    (r) => r.agentType === "hr" || r.kind === "behavioral"
  );
  if (!hrTouched)
    return { line: t("agentCards.willStartTracking"), meta: null };
  return {
    line: tPlural("agentCards.weeksEvaluated", dashboard.weeksCompleted, { n: dashboard.weeksCompleted }),
    meta: t("agentCards.growthViewReady"),
  };
}

const AGENT_HREF: Record<AgentId, string> = {
  manager: "/meeting",
  mentor: "/meeting",
  hr: "/meeting",
};

function AgentCard({ id, meta, dashboard, reviews, index }: {
  id: AgentId;
  meta: AgentMeta;
  dashboard: Dashboard;
  reviews: Review[];
  index: number;
}) {
  const status = useAgentStatus(id, dashboard, reviews);
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.15 + 0.05 * index, duration: 0.3, ease: "easeOut" }}
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
            <span className="ms-auto font-mono text-[10px] text-text-muted">
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
}

export function AgentCards({ dashboard, reviews, extraAgents }: AgentCardsProps) {
  const { t } = useLocale();
  const agents = useAgents();
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {AGENT_ORDER.map((id, i) => (
        <AgentCard key={id} id={id} meta={agents[id]} dashboard={dashboard} reviews={reviews} index={i} />
      ))}
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
          <p className="mt-2 text-xs text-text-secondary">{t("agentCards.addedDuringOnboarding")}</p>
          <p className="mt-3 text-sm leading-relaxed text-text-primary">
            {agent.description}
          </p>
        </motion.div>
      ))}
    </div>
  );
}
