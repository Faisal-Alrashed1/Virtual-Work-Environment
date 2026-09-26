"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  Settings as SettingsIcon,
  Terminal,
  Sparkles,
  AlertCircle,
} from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { ApiError, type ApiAgentType } from "@/lib/api";
import {
  assignNextTask,
  DEFAULT_TASK_CHAT_AGENT,
  fetchTaskDetail,
  mergeMessages,
  fetchTasks,
  postUserMessage,
  requestMentorReview,
  startTask,
  submitTask,
  taskChatReply,
  type Task,
} from "@/lib/tasks";
import { TaskRail } from "@/components/workspace/task-rail";
import {
  TaskWorkspace,
  type SubmitPayload,
} from "@/components/workspace/task-workspace";
import { AgentsMeeting } from "@/components/workspace/agents-meeting";
import { fetchMyExtraAgents, type ExtraAgent } from "@/lib/team";
import { useLocale } from "@/lib/i18n/locale";
import { AccountMenu } from "@/components/nav/account-menu";
import { IconLink } from "@/components/nav/icon-link";
import { ThemeToggle } from "@/components/theme-toggle";
import { LocaleToggle } from "@/components/locale-toggle";

// How often to refresh a task whose specialist discussion is still being written, and how long
// to keep trying (a discussion normally takes 15-40 seconds).
const ROUNDTABLE_POLL_MS = 2500;
const ROUNDTABLE_POLL_MAX_MS = 150_000;

export default function WorkspacePage() {
  const { user, loading: authLoading } = useRequireAuth();
  const { t, locale } = useLocale();

  const [tasks, setTasks] = useState<Task[]>([]);
  const [extraAgents, setExtraAgents] = useState<ExtraAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [assigning, setAssigning] = useState(false);
  const [busy, setBusy] = useState<{
    taskId: string;
    kind: "review" | "reply";
  } | null>(null);
  // Who the graduate is currently addressing in the selected task's
  // thread — defaults to the Mentor (see lib/tasks.ts's
  // DEFAULT_TASK_CHAT_AGENT) every time a different task is opened, so
  // switching tasks never leaves you "still talking to DevOps" by accident.
  const [chatAgent, setChatAgent] = useState<ApiAgentType>(
    DEFAULT_TASK_CHAT_AGENT,
  );

  const refresh = useCallback(async () => {
    try {
      const list = await fetchTasks();
      setTasks(list);
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
      setError(
        err instanceof ApiError ? err.message : t("workspace.loadTasksError"),
      );
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (user) refresh();
    if (user)
      fetchMyExtraAgents()
        .then(setExtraAgents)
        .catch(() => {});
  }, [user, refresh]);

  // The specialists' discussion runs in the BACKGROUND after the Mentor's review
  // (docs/BACKGROUND_ROUNDTABLE.md). While a task says it is still going, refresh it every
  // couple of seconds so each comment appears as it is written. It stops by itself once the
  // server says the discussion is done, and after a hard cap in case that never arrives.
  const pollTaskId = tasks.find((t) => t.roundtableRunning)?.id ?? null;
  useEffect(() => {
    if (!pollTaskId) return;
    let cancelled = false;
    const startedAt = Date.now();
    const timer = setInterval(async () => {
      if (Date.now() - startedAt > ROUNDTABLE_POLL_MAX_MS) {
        clearInterval(timer);
        // Give up quietly rather than leave a "discussing..." note that never clears.
        setTasks((prev) =>
          prev.map((t) =>
            t.id === pollTaskId ? { ...t, roundtableRunning: false } : t,
          ),
        );
        return;
      }
      try {
        const detail = await fetchTaskDetail(pollTaskId);
        if (cancelled) return;
        setTasks((prev) =>
          prev.map((t) =>
            t.id === detail.id
              ? {
                  ...detail,
                  messages: mergeMessages(t.messages, detail.messages),
                }
              : t,
          ),
        );
      } catch {
        // A missed refresh is harmless: the next one catches up.
      }
    }, ROUNDTABLE_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [pollTaskId]);

  const selected = tasks.find((t) => t.id === selectedId) ?? null;

  async function openTask(id: string) {
    setSelectedId(id);
    setChatAgent(DEFAULT_TASK_CHAT_AGENT);
    try {
      const detail = await fetchTaskDetail(id);
      setTasks((prev) => prev.map((t) => (t.id === id ? detail : t)));
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : t("workspace.loadTaskError"),
      );
    }
  }

  async function handleAskManager() {
    setAssigning(true);
    setError(null);
    try {
      const task = await assignNextTask();
      setTasks((prev) => [task, ...prev]);
      setSelectedId(task.id);
      setChatAgent(DEFAULT_TASK_CHAT_AGENT);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : t("workspace.assignError"),
      );
    } finally {
      setAssigning(false);
    }
  }

  async function handleAdvance(payload?: SubmitPayload) {
    if (!selected) return;
    try {
      if (selected.status === "todo") {
        const task = await startTask(selected.id);
        setTasks((prev) => prev.map((t) => (t.id === task.id ? task : t)));
      } else if (selected.status === "in_progress" && payload) {
        const task = await submitTask(selected.id, payload);
        setTasks((prev) => prev.map((t) => (t.id === task.id ? task : t)));
        setBusy({ taskId: task.id, kind: "review" });
        try {
          const reviewed = await requestMentorReview(task.id);
          setTasks((prev) =>
            prev.map((t) => (t.id === reviewed.id ? reviewed : t)),
          );
        } catch (err) {
          setError(
            err instanceof ApiError ? err.message : t("workspace.reviewError"),
          );
        } finally {
          setBusy(null);
        }
      }
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : t("workspace.updateError"),
      );
    }
  }

  async function handleSendMessage(content: string, agent: ApiAgentType) {
    if (!selected) return;
    const taskId = selected.id;
    try {
      const message = await postUserMessage(taskId, content);
      setTasks((prev) =>
        prev.map((t) =>
          t.id === taskId ? { ...t, messages: [...t.messages, message] } : t,
        ),
      );
      setBusy({ taskId, kind: "reply" });
      try {
        const reply = await taskChatReply(taskId, agent);
        setTasks((prev) =>
          prev.map((t) =>
            t.id === taskId ? { ...t, messages: [...t.messages, reply] } : t,
          ),
        );
      } catch (err) {
        setError(
          err instanceof ApiError ? err.message : t("workspace.replyError"),
        );
      } finally {
        setBusy(null);
      }
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : t("workspace.sendMessageError"),
      );
    }
  }

  if (authLoading || !user) {
    return (
      <main className="flex min-h-screen flex-1 items-center justify-center bg-bg-base text-text-primary">
        <div className="flex items-center gap-2 rounded border border-border bg-bg-surface px-4 py-3 font-mono text-xs text-text-muted">
          <span className="h-2 w-2 animate-ping rounded-full bg-accent" />
          <span>{t("common.loading")}</span>
        </div>
      </main>
    );
  }

  const taskBusy = selected && busy?.taskId === selected.id ? busy.kind : null;
  const BackArrow = locale === "ar" ? ArrowRight : ArrowLeft;

  return (
    <main className="grid h-dvh grid-rows-[auto_1fr] bg-bg-base text-text-primary selection:bg-accent selection:text-accent-text">
      {/* Top Engineering Workspace Bar */}
      <header className="z-20 flex h-14 items-center justify-between border-b border-border bg-bg-surface/90 px-6 backdrop-blur-md">
        <div className="flex items-center gap-4">
          <Link
            href="/board"
            className="group flex items-center gap-2 font-mono text-xs text-text-muted transition-colors hover:text-text-primary"
          >
            <BackArrow className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5 rtl:group-hover:translate-x-0.5" />
            <span>{t("nav.venvBoard")}</span>
            <span className="text-border-strong">/</span>
            <span className="text-[10px] text-text-muted transition-colors group-hover:text-text-secondary">
              IDE_WORKSPACE
            </span>
          </Link>

          <div className="hidden items-center gap-2 border-s border-border ps-4 sm:flex">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            <h1 className="font-mono text-xs font-medium uppercase tracking-wider text-text-primary">
              {t("nav.workspaceTitle")}
            </h1>
          </div>
        </div>

        {/* Global Toolbar Cluster */}
        <div className="flex items-center gap-2">
          <IconLink href="/settings" label={t("nav.settings")}>
            <SettingsIcon className="h-3.5 w-3.5" strokeWidth={1.75} />
          </IconLink>

          <div className="mx-1 h-4 border-s border-border" />

          <AccountMenu email={user.email} />
          <LocaleToggle className="bg-bg-base" />
          <ThemeToggle className="bg-bg-base" />
        </div>
      </header>

      {/* Global Error Banner */}
      {error && (
        <div className="flex items-center gap-2 border-b border-danger/30 bg-danger/10 px-6 py-2.5 text-xs text-danger">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" />
          <p className="flex-1 font-mono">{error}</p>
        </div>
      )}

      {/* Primary Workspace Viewport */}
      {loading ? (
        <div className="flex flex-1 items-center justify-center bg-blueprint-grid">
          <div className="flex items-center gap-2 rounded border border-border bg-bg-surface px-4 py-3 font-mono text-xs text-text-muted">
            <span className="h-2 w-2 animate-ping rounded-full bg-accent" />
            <span>{t("workspace.loadingWorkspace")}</span>
          </div>
        </div>
      ) : (
        <div className="grid min-h-0 grid-cols-1 md:grid-cols-[280px_minmax(0,1fr)] xl:grid-cols-[280px_minmax(0,1fr)_380px]">
          {/* Rail Pane (Left) */}
          <div className="min-h-0 border-e border-border bg-bg-surface/50">
            <TaskRail
              tasks={tasks}
              selectedId={selectedId}
              onSelect={openTask}
              onAskManager={handleAskManager}
              assigning={assigning}
            />
          </div>

          {/* Central Workspace & Right Agent Thread */}
          {selected ? (
            <>
              {/* Task Detail & Submission Form (Center) */}
              <div className="min-h-0 border-e border-border bg-bg-base">
                <TaskWorkspace
                  task={selected}
                  busy={taskBusy}
                  onAdvance={handleAdvance}
                />
              </div>

              {/* Agents Meeting Thread (Right) */}
              <div className="hidden min-h-0 bg-bg-surface/30 xl:block">
                <AgentsMeeting
                  task={selected}
                  busy={taskBusy}
                  extraAgents={extraAgents}
                  chatAgent={chatAgent}
                  onChangeChatAgent={setChatAgent}
                  onSendMessage={handleSendMessage}
                />
              </div>
            </>
          ) : (
            /* Empty State Panel */
            <div className="relative flex flex-col items-center justify-center bg-blueprint-grid p-6 text-center md:col-span-1 xl:col-span-2">
              <div className="relative w-full max-w-md rounded border border-border bg-bg-surface p-8">
                {/* Corner markers */}
                <div className="pointer-events-none absolute -start-[5px] -top-[5px] font-mono text-xs leading-none text-text-muted">
                  +
                </div>
                <div className="pointer-events-none absolute -end-[5px] -top-[5px] font-mono text-xs leading-none text-text-muted">
                  +
                </div>
                <div className="pointer-events-none absolute -bottom-[5px] -start-[5px] font-mono text-xs leading-none text-text-muted">
                  +
                </div>
                <div className="pointer-events-none absolute -bottom-[5px] -end-[5px] font-mono text-xs leading-none text-text-muted">
                  +
                </div>

                <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full border border-border bg-bg-base text-accent-ink">
                  <Terminal className="h-5 w-5" strokeWidth={1.75} />
                </div>

                <p className="mt-4 font-mono text-[11px] uppercase tracking-wider text-text-muted">
                  DISPATCH_QUEUE // EMPTY
                </p>
                <h2 className="mt-2 text-lg font-medium text-text-primary">
                  {t("workspace.noTaskSelected")}
                </h2>

                <div className="mt-6 border-t border-border pt-6">
                  <button
                    type="button"
                    onClick={handleAskManager}
                    disabled={assigning}
                    className="inline-flex h-9 items-center justify-center gap-2 rounded border border-accent bg-accent px-5 font-mono text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Sparkles className="h-3.5 w-3.5" />
                    <span>
                      {assigning
                        ? t("workspace.managerThinking")
                        : t("workspace.askManagerTask")}
                    </span>
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </main>
  );
}
