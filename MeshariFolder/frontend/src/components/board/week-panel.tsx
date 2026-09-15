"use client";

import { Panel } from "reactflow";
import { motion } from "framer-motion";
import type { Project, Week } from "@/lib/projects";
import { timeUntil } from "@/lib/format";

interface WeekStatusPanelProps {
  loading: boolean;
  project: Project | null;
  week: Week | null;
  onSelect: () => void;
}

/**
 * The board's one persistent "quick glance" readout — everything else on
 * the board is click-to-open. Styled like a small spec plate bolted onto
 * the blueprint (DESIGN.md's floor-plan idea), not a card: hairline
 * border, mono numbers, no shadow. Lives in a ReactFlow <Panel>, which is
 * fixed to a corner of the canvas and never scrolls or pans with it — so
 * it can't ever push the page into scrolling, no matter how much detail
 * gets added later.
 */
export function WeekStatusPanel({
  loading,
  project,
  week,
  onSelect,
}: WeekStatusPanelProps) {
  return (
    <Panel position="top-right">
      <motion.button
        type="button"
        onClick={onSelect}
        disabled={!week}
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5, duration: 0.35, ease: "easeOut" }}
        className="w-[240px] rounded border border-border bg-bg-surface px-4 py-3 text-left transition-colors enabled:cursor-pointer enabled:hover:border-border-strong disabled:cursor-default"
      >
        <div className="flex items-center justify-between">
          <span className="font-mono text-[11px] text-text-muted">
            week_status
          </span>
          {week && (
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{
                backgroundColor:
                  week.status === "active"
                    ? "var(--agent-manager)"
                    : "var(--text-muted)",
              }}
            />
          )}
        </div>

        {loading ? (
          <p className="mt-2 text-sm text-text-muted">Loading...</p>
        ) : !project || !week ? (
          <p className="mt-2 text-sm leading-relaxed text-text-secondary">
            No project yet — ask the manager for your first task to start one.
          </p>
        ) : (
          <>
            <p className="mt-2 line-clamp-1 text-xs text-text-secondary">
              {project.title}
            </p>
            <p className="mt-1 text-sm font-medium text-text-primary">
              Week {week.weekNumber}
            </p>
            <p className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-text-secondary">
              {week.bigTaskTitle}
            </p>

            <div className="mt-3 flex items-center gap-2">
              <div className="flex gap-1">
                {week.subtasksPlan.map((_, i) => (
                  <span
                    key={i}
                    className="h-1.5 w-1.5 rounded-full"
                    style={{
                      backgroundColor:
                        i < week.subtasksReleased
                          ? "var(--agent-manager)"
                          : "var(--border-strong)",
                    }}
                  />
                ))}
              </div>
              <span className="font-mono text-[11px] text-text-muted">
                {week.subtasksReleased}/{week.subtasksPlan.length}
              </span>
            </div>

            <p className="mt-2 font-mono text-[11px] text-text-muted">
              {week.status === "completed"
                ? "week complete"
                : `week ends ${timeUntil(week.targetEndAt)}`}
            </p>
          </>
        )}
      </motion.button>
    </Panel>
  );
}
