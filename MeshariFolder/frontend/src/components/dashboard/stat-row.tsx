"use client";

import { motion } from "framer-motion";
import type { Dashboard } from "@/lib/dashboard";
import { useLocale } from "@/lib/i18n/locale";

interface StatRowProps {
  dashboard: Dashboard;
}

interface Stat {
  label: string;
  value: string;
  sub: string;
}

function useStats(d: Dashboard): Stat[] {
  const { t, tPlural } = useLocale();
  return [
    {
      label: t("statRow.tasksDone"),
      value: String(d.tasksCompleted),
      sub: d.tasksTotal > 0 ? t("statRow.ofAssigned", { n: d.tasksTotal }) : t("statRow.noneYet"),
    },
    {
      label: t("statRow.onTimeRate"),
      // null (nothing judged yet) shows a dash, not a misleading 0/100%.
      value: d.onTimeRate === null ? "—" : `${Math.round(d.onTimeRate * 100)}%`,
      sub: t("statRow.submittedBeforeDeadline"),
    },
    {
      label: t("statRow.avgScore"),
      value: d.averageScore === null ? "—" : d.averageScore.toFixed(1),
      sub:
        d.reviewsCount > 0
          ? tPlural("statRow.acrossReviews", d.reviewsCount, { n: d.reviewsCount })
          : t("statRow.noReviewsYet"),
    },
    {
      label: t("statRow.weeksDone"),
      value: String(d.weeksCompleted),
      sub: d.weeksTotal > 0 ? t("statRow.ofStarted", { n: d.weeksTotal }) : t("statRow.noneYet"),
    },
  ];
}

export function StatRow({ dashboard }: StatRowProps) {
  const stats = useStats(dashboard);
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
