"use client";

import { useEffect, useRef, useState } from "react";
import { Users } from "lucide-react";
import { resolveAgentDisplay, useAgents, useLocale } from "@/lib/i18n/locale";
import type { ApiAgentType } from "@/lib/api";
import { TASK_CHAT_AGENTS, type Task } from "@/lib/tasks";
import type { ExtraAgent } from "@/lib/team";
import { timeAgo } from "@/lib/format";

interface AgentsMeetingProps {
  task: Task;
  busy: "review" | "reply" | null;
  extraAgents: ExtraAgent[];
  /** Who the graduate is currently addressing on this task — defaults to
   * the Mentor. See lib/tasks.ts's TASK_CHAT_AGENTS. */
  chatAgent: ApiAgentType;
  onChangeChatAgent: (agent: ApiAgentType) => void;
  onSendMessage: (content: string, agent: ApiAgentType) => void;
}

/**
 * The task-scoped chat thread. It's task-scoped on purpose (a
 * conversation here is always about the work at hand), so it lives
 * beside the task rather than on a separate page: one screen shows the
 * work and the discussion of it at once.
 *
 * Unlike the old single-Manager thread, the graduate can now see *who
 * they're working with* and switch: the Mentor by default (day-to-day
 * help on this task, like a senior engineer), the Manager (big-picture
 * only — it redirects hands-on asks back to the Mentor), or any
 * technical agent on their roster (Security Reviewer/Data Reviewer/
 * DevOps) for a direct question about this task. The thread itself still
 * shows everyone who has spoken in it, colored by who spoke — including
 * the roundtable's specialists once the task is submitted.
 */
export function AgentsMeeting({
  task,
  busy,
  extraAgents,
  chatAgent,
  onChangeChatAgent,
  onSendMessage,
}: AgentsMeetingProps) {
  const { t } = useLocale();
  const agents = useAgents();
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  // Available switcher options: the two defaults (Mentor first — it's who
  // the graduate should be talking to day to day) plus any technical
  // roster agent they've actually added.
  const extraIds = new Set(extraAgents.map((a) => a.id));
  const availableChatAgents = TASK_CHAT_AGENTS.filter(
    (id) => id === "mentor" || id === "manager" || extraIds.has(id)
  );

  const activeMeta = resolveAgentDisplay(chatAgent, agents, extraAgents);

  // Keep the latest message in view as the conversation grows / an agent
  // reply lands.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [task.messages.length, busy, task.roundtableRunning]);

  function send() {
    const content = draft.trim();
    if (!content || busy === "reply") return;
    onSendMessage(content, chatAgent);
    setDraft("");
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <Users className="h-3.5 w-3.5 text-text-muted" />
        <p className="font-mono text-[11px] text-text-muted">{t("agentsMeeting.eyebrow")}</p>
      </div>

      {/* Who you're working with on this task right now — the switcher. */}
      <div className="border-b border-border px-3 py-2.5">
        <p className="px-1 font-mono text-[10px] uppercase tracking-wide text-text-muted">
          {t("agentsMeeting.workingWith")}
        </p>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {availableChatAgents.map((id) => {
            const meta = resolveAgentDisplay(id, agents, extraAgents);
            const active = id === chatAgent;
            return (
              <button
                key={id}
                type="button"
                onClick={() => onChangeChatAgent(id)}
                disabled={busy === "reply"}
                className={`flex items-center gap-1.5 rounded border px-2.5 py-1 text-xs transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
                  active
                    ? "border-accent bg-accent/10 text-text-primary"
                    : "border-border text-text-secondary hover:border-border-strong hover:text-text-primary"
                }`}
              >
                <span
                  className="h-1.5 w-1.5 rounded-full"
                  style={
                    meta.colorVar
                      ? { backgroundColor: `var(${meta.colorVar})` }
                      : { backgroundColor: "var(--text-muted)" }
                  }
                />
                {meta.name}
              </button>
            );
          })}
        </div>
      </div>

      <div ref={scrollRef} className="thin-scrollbar min-h-0 flex-1 overflow-y-auto p-4">
        {task.messages.length === 0 && !task.roundtableRunning ? (
          <p className="py-6 text-center text-xs text-text-muted">
            {t("agentsMeeting.noDiscussion", { name: activeMeta.name })}
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            {task.messages.map((m) => {
              const meta = m.agentType ? resolveAgentDisplay(m.agentType, agents, extraAgents) : null;
              const isUser = !meta;
              return (
                <div
                  key={m.id}
                  className={`max-w-[85%] rounded border px-3 py-2 ${
                    isUser
                      ? "self-end border-accent/40 bg-accent/10"
                      : "self-start border-border bg-bg-surface"
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    {meta && (
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${meta.colorVar ? "" : "bg-text-muted"}`}
                        style={meta.colorVar ? { backgroundColor: `var(${meta.colorVar})` } : undefined}
                      />
                    )}
                    <span className="font-mono text-[10px] text-text-muted">
                      {meta ? meta.name : t("common.you")} · {timeAgo(m.createdAt)}
                    </span>
                  </div>
                  <p className="mt-1 whitespace-pre-line text-sm text-text-primary">
                    {m.content}
                  </p>
                </div>
              );
            })}
            {busy === "reply" && (
              <div className="max-w-[85%] self-start rounded border border-dashed border-border px-3 py-2">
                <p className="font-mono text-[11px] text-text-muted">
                  {t("agentsMeeting.agentTyping", { name: activeMeta.name })}
                </p>
              </div>
            )}
            {task.roundtableRunning && (
              <div className="max-w-[85%] self-start rounded border border-dashed border-border px-3 py-2">
                <p className="font-mono text-[11px] text-text-muted">
                  {t("agentsMeeting.teamDiscussing")}
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="border-t border-border p-3">
        <div className="flex items-end gap-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            rows={2}
            placeholder={t("agentsMeeting.messagePlaceholder", { name: activeMeta.name })}
            disabled={busy === "reply"}
            className="thin-scrollbar min-h-0 flex-1 resize-none rounded border border-border bg-bg-surface px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-border-strong focus:outline-none disabled:opacity-50"
          />
          <button
            type="button"
            onClick={send}
            disabled={!draft.trim() || busy === "reply"}
            className="shrink-0 rounded border border-accent bg-accent px-4 py-2 text-sm font-medium text-accent-text transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy === "reply" ? t("common.sendBusy") : t("common.send")}
          </button>
        </div>
      </div>
    </div>
  );
}
