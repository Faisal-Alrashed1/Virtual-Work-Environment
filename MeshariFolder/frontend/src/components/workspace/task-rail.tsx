"use client";

import { STATUS_LABEL, STATUS_ORDER, type Task, type TaskStatus } from "@/lib/tasks";
import { AGENTS } from "@/lib/agents";
import { timeUntil } from "@/lib/format";

interface TaskRailProps {
  tasks: Task[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onAskManager: () => void;
  assigning: boolean;
}

const STATUS_DOT: Record<TaskStatus, string> = {
  todo: "var(--border-strong)",
  in_progress: "var(--agent-manager)",
  submitted: "var(--agent-mentor)",
  reviewed: "var(--agent-hr)",
};

export function TaskRail({
  tasks,
  selectedId,
  onSelect,
  onAskManager,
  assigning,
}: TaskRailProps) {
  const grouped: Record<TaskStatus, Task[]> = {
    todo: [],
    in_progress: [],
    submitted: [],
    reviewed: [],
  };
  for (const t of tasks) grouped[t.status].push(t);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <p className="font-mono text-[11px] text-text-muted">
          tasks · {tasks.length}
        </p>
        <button
          type="button"
          onClick={onAskManager}
          disabled={assigning}
          className="rounded border border-accent bg-accent px-3 py-1.5 text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50"
        >
          {assigning ? "Thinking..." : "+ Ask manager"}
        </button>
      </div>

      <div className="thin-scrollbar min-h-0 flex-1 overflow-y-auto">
        {tasks.length === 0 ? (
          <p className="px-4 py-8 text-center text-xs text-text-muted">
            No tasks yet — ask your manager for one.
          </p>
        ) : (
          STATUS_ORDER.map((status) =>
            grouped[status].length === 0 ? null : (
              <div key={status} className="border-b border-border/60 py-2">
                <p className="px-4 py-1 font-mono text-[10px] uppercase tracking-wide text-text-muted">
                  {STATUS_LABEL[status]} · {grouped[status].length}
                </p>
                {grouped[status].map((task) => {
                  const selected = task.id === selectedId;
                  return (
                    <button
                      key={task.id}
                      type="button"
                      onClick={() => onSelect(task.id)}
                      className={`flex w-full flex-col gap-1 border-l-2 px-4 py-2.5 text-left transition-colors ${
                        selected
                          ? "border-accent bg-bg-surface"
                          : "border-transparent hover:bg-bg-surface"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className="h-1.5 w-1.5 shrink-0 rounded-full"
                          style={{ backgroundColor: STATUS_DOT[task.status] }}
                        />
                        <span className="line-clamp-1 text-sm text-text-primary">
                          {task.title}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 pl-3.5">
                        <span className="font-mono text-[10px] text-text-muted">
                          {AGENTS[task.createdByAgent].id}
                        </span>
                        {task.deadline && task.status !== "reviewed" && (
                          <span
                            className={`font-mono text-[10px] ${
                              task.isLate ? "text-danger" : "text-text-muted"
                            }`}
                          >
                            due {timeUntil(task.deadline)}
                          </span>
                        )}
                        {task.status === "reviewed" && task.isLate && (
                          <span className="font-mono text-[10px] text-danger">
                            late
                          </span>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            )
          )
        )}
      </div>
    </div>
  );
}
