"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRequireAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";
import {
  assignNextTask,
  fetchTaskDetail,
  fetchTasks,
  managerReply,
  postUserMessage,
  requestMentorReview,
  startTask,
  submitTask,
  type Task,
} from "@/lib/tasks";
import { TaskRail } from "@/components/workspace/task-rail";
import { TaskWorkspace, type SubmitPayload } from "@/components/workspace/task-workspace";
import { AgentsMeeting } from "@/components/workspace/agents-meeting";
import { fetchMyExtraAgents, type ExtraAgent } from "@/lib/team";
import { useLocale } from "@/lib/i18n/locale";
import { ThemeToggle } from "@/components/theme-toggle";
import { LocaleToggle } from "@/components/locale-toggle";

// GET /tasks and the status/submit endpoints return tasks without their
// thread. Replacing a task with one of those would blank its agents panel,
// so keep the thread that's already loaded (a thread never shrinks).
function keepThread(next: Task, prev: Task[]): Task {
  if (next.messages.length > 0) return next;
  const loaded = prev.find((t) => t.id === next.id);
  return loaded ? { ...next, messages: loaded.messages } : next;
}

export default function WorkspacePage() {
  const { user, loading: authLoading } = useRequireAuth();
  const { t } = useLocale();

  const [tasks, setTasks] = useState<Task[]>([]);
  const [extraAgents, setExtraAgents] = useState<ExtraAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [assigning, setAssigning] = useState(false);
  const [busy, setBusy] = useState<{ taskId: string; kind: "review" | "reply" } | null>(
    null
  );

  const refresh = useCallback(async () => {
    try {
      const list = await fetchTasks();
      setTasks((prev) => list.map((task) => keepThread(task, prev)));
      setError(null);
      // Auto-select the most sensible task: the open one if any, else the
      // most recent. Keeps the center panel from ever being empty when
      // there's something to show.
      setSelectedId((prev) => {
        if (prev && list.some((t) => t.id === prev)) return prev;
        const open = list.find((t) => t.status !== "reviewed");
        return open?.id ?? list[0]?.id ?? null;
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("workspace.loadTasksError"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (user) refresh();
    if (user) fetchMyExtraAgents().then(setExtraAgents).catch(() => {});
  }, [user, refresh]);

  const selected = tasks.find((t) => t.id === selectedId) ?? null;

  const loadThread = useCallback(
    async (id: string) => {
      try {
        const detail = await fetchTaskDetail(id);
        setTasks((prev) => prev.map((t) => (t.id === id ? detail : t)));
      } catch (err) {
        setError(err instanceof ApiError ? err.message : t("workspace.loadTaskError"));
      }
    },
    [t]
  );

  // Load the thread whenever a task becomes selected — including the one
  // auto-selected on page load and a newly assigned one, not only on click.
  // Before, the agents panel stayed empty until the task was clicked.
  useEffect(() => {
    // setState only runs after the fetch resolves, same as refresh() above.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (selectedId) loadThread(selectedId);
  }, [selectedId, loadThread]);

  function openTask(id: string) {
    // A different task: the effect above loads it. The same task again:
    // reload its thread (e.g. to pick up new agent replies).
    if (id === selectedId) loadThread(id);
    else setSelectedId(id);
  }

  async function handleAskManager() {
    setAssigning(true);
    setError(null);
    try {
      const task = await assignNextTask();
      setTasks((prev) => [task, ...prev]);
      setSelectedId(task.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("workspace.assignError"));
    } finally {
      setAssigning(false);
    }
  }

  async function handleAdvance(payload?: SubmitPayload) {
    if (!selected) return;
    try {
      if (selected.status === "todo") {
        const task = await startTask(selected.id);
        setTasks((prev) => prev.map((t) => (t.id === task.id ? keepThread(task, prev) : t)));
      } else if (selected.status === "in_progress" && payload) {
        const task = await submitTask(selected.id, payload);
        setTasks((prev) => prev.map((t) => (t.id === task.id ? keepThread(task, prev) : t)));
        setBusy({ taskId: task.id, kind: "review" });
        try {
          const reviewed = await requestMentorReview(task.id);
          setTasks((prev) => prev.map((t) => (t.id === reviewed.id ? reviewed : t)));
        } catch (err) {
          setError(err instanceof ApiError ? err.message : t("workspace.reviewError"));
        } finally {
          setBusy(null);
        }
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("workspace.updateError"));
    }
  }

  async function handleSendMessage(content: string) {
    if (!selected) return;
    const taskId = selected.id;
    try {
      const message = await postUserMessage(taskId, content);
      setTasks((prev) =>
        prev.map((t) =>
          t.id === taskId ? { ...t, messages: [...t.messages, message] } : t
        )
      );
      setBusy({ taskId, kind: "reply" });
      try {
        const reply = await managerReply(taskId);
        setTasks((prev) =>
          prev.map((t) =>
            t.id === taskId ? { ...t, messages: [...t.messages, reply] } : t
          )
        );
      } catch (err) {
        setError(err instanceof ApiError ? err.message : t("workspace.replyError"));
      } finally {
        setBusy(null);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("workspace.sendMessageError"));
    }
  }

  if (authLoading || !user) {
    return (
      <main className="flex flex-1 items-center justify-center">
        <p className="text-sm text-text-muted">{t("common.loading")}</p>
      </main>
    );
  }

  const taskBusy = selected && busy?.taskId === selected.id ? busy.kind : null;

  return (
    <main className="grid h-dvh grid-rows-[auto_1fr]">
      <header className="flex items-center justify-between border-b border-border px-6 py-4">
        <div>
          <Link
            href="/board"
            className="font-mono text-xs text-text-muted hover:text-text-secondary"
          >
            {t("nav.venvBoard")}
          </Link>
          <h1 className="mt-1 text-lg font-medium text-text-primary">{t("nav.workspaceTitle")}</h1>
        </div>
        <div className="flex items-center gap-3">
          <span dir="ltr" className="hidden font-mono text-xs text-text-muted lg:inline">
            {user.email}
          </span>
          <Link
            href="/logout"
            className="rounded border border-border px-3 py-1 text-xs text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
          >
            {t("common.logOut")}
          </Link>
          <LocaleToggle />
          <ThemeToggle />
        </div>
      </header>

      {error && (
        <div className="border-b border-border bg-bg-surface px-6 py-2">
          <p className="text-sm text-danger">{error}</p>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center">
          <p className="text-sm text-text-muted">{t("workspace.loadingWorkspace")}</p>
        </div>
      ) : (
        // Three regions: task rail | task detail | agents meeting. The two
        // side panels are fixed-width; the center flexes. On smaller
        // screens the meeting panel drops (it's reachable by scrolling the
        // center on tablet) and the rail narrows.
        <div className="grid min-h-0 grid-cols-1 md:grid-cols-[260px_minmax(0,1fr)] xl:grid-cols-[260px_minmax(0,1fr)_360px]">
          <div className="min-h-0 border-e border-border">
            <TaskRail
              tasks={tasks}
              selectedId={selectedId}
              onSelect={openTask}
              onAskManager={handleAskManager}
              assigning={assigning}
            />
          </div>

          {selected ? (
            <>
              <div className="min-h-0 border-e border-border">
                <TaskWorkspace
                  task={selected}
                  busy={taskBusy}
                  onAdvance={handleAdvance}
                  discussion={
                    // The side panel below is hidden under the xl breakpoint;
                    // there the discussion shows under the task instead.
                    <AgentsMeeting
                      task={selected}
                      busy={taskBusy}
                      extraAgents={extraAgents}
                      onSendMessage={handleSendMessage}
                    />
                  }
                />
              </div>
              <div className="hidden min-h-0 xl:block">
                <AgentsMeeting
                  task={selected}
                  busy={taskBusy}
                  extraAgents={extraAgents}
                  onSendMessage={handleSendMessage}
                />
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center gap-3 md:col-span-1 xl:col-span-2">
              <p className="text-sm text-text-secondary">
                {t("workspace.noTaskSelected")}
              </p>
              <button
                type="button"
                onClick={handleAskManager}
                disabled={assigning}
                className="rounded border border-accent bg-accent px-5 py-2.5 text-sm font-medium text-accent-text transition-colors hover:bg-accent-strong disabled:opacity-50"
              >
                {assigning ? t("workspace.managerThinking") : t("workspace.askManagerTask")}
              </button>
            </div>
          )}
        </div>
      )}
    </main>
  );
}
