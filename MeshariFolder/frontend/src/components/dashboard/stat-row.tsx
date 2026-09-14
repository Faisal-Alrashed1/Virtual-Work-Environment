"use client";

import { motion } from "framer-motion";
import type { Dashboard } from "@/lib/dashboard";

interface StatRowProps {
  dashboard: Dashboard;
}

interface Stat {
  label: string;
  value: string;
  sub: string;
}

function buildStats(d: Dashboard): Stat[] {
  return [
    {
      label: "tasks_done",
      value: String(d.tasksCompleted),
      sub: d.tasksTotal > 0 ? `of ${d.tasksTotal} assigned` : "none yet",
    },
    {
      label: "on_time_rate",
      // null (nothing judged yet) shows a dash, not a misleading 0/100%.
      value: d.onTimeRate === null ? "—" : `${Math.round(d.onTimeRate * 100)}%`,
      sub: "submitted before deadline",
    },
    {
      label: "avg_score",
      value: d.averageScore === null ? "—" : d.averageScore.toFixed(1),
      sub: d.reviewsCount > 0 ? `across ${d.reviewsCount} reviews` : "no reviews yet",
    },
    {
      label: "weeks_done",
      value: String(d.weeksCompleted),
      sub: d.weeksTotal > 0 ? `of ${d.weeksTotal} started` : "none yet",
    },
  ];
}

export function StatRow({ dashboard }: StatRowProps) {
  const stats = buildStats(dashboard);
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {stats.map((stat, i) => (
        <motion.div
          key={stat.label}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 * i, duration: 0.3, ease: "easeOut" }}
          className="rounded border border-border bg-bg-surface px-4 py-3"
        >
          <p className="font-mono text-[11px] text-text-muted">{stat.label}</p>
          <p className="mt-1 text-2xl font-medium text-text-primary">
            {stat.value}
          </p>
          <p className="mt-0.5 text-xs text-text-secondary">{stat.sub}</p>
        </motion.div>
      ))}
    </div>
  );
}
