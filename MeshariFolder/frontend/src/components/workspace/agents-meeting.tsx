"use client";

import { useEffect, useRef, useState } from "react";
import { Users } from "lucide-react";
import { agentDisplay } from "@/lib/agent-display";
import type { ExtraAgent } from "@/lib/team";
import type { Task } from "@/lib/tasks";
import { timeAgo } from "@/lib/format";

interface AgentsMeetingProps {
  task: Task;
  busy: "review" | "reply" | null;
  extraAgents: ExtraAgent[];
  onSendMessage: (content: string) => void;
}

/**
 * The "agents meeting" — the running conversation with agents about the
 * current task. It's task-scoped on purpose (a meeting is always about
 * something), so it lives beside the task rather than on a separate page:
 * one screen shows the work and the discussion of it at once. The Manager
 * answers in-thread, and Stage 2's co-reviewers (Security Reviewer/Data
 * Reviewer/DevOps) post here too after the Mentor's review, if they're on
 * the graduate's team — this same panel renders them all, colored by who
 * spoke.
 */
export function AgentsMeeting({ task, busy, extraAgents, onSendMessage }: AgentsMeetingProps) {
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  // Keep the latest message in view as the conversation grows / an agent
  // reply lands.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [task.messages.length, busy]);

  function send() {
    const content = draft.trim();
    if (!content || busy === "reply") return;
    onSendMessage(content);
    setDraft("");
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <Users className="h-3.5 w-3.5 text-text-muted" />
        <p className="font-mono text-[11px] text-text-muted">agents_meeting</p>
      </div>

      <div ref={scrollRef} className="thin-scrollbar min-h-0 flex-1 overflow-y-auto p-4">
        {task.messages.length === 0 ? (
          <p className="py-6 text-center text-xs text-text-muted">
            No discussion yet. Ask a question or share where you&apos;re at —
            your manager will respond here.
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            {task.messages.map((m) => {
              const meta = m.agentType ? agentDisplay(m.agentType, extraAgents) : null;
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
                      {meta ? meta.name : "You"} · {timeAgo(m.createdAt)}
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
                  Manager is typing...
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
            placeholder="Message the team... (Enter to send)"
            disabled={busy === "reply"}
            className="thin-scrollbar min-h-0 flex-1 resize-none rounded border border-border bg-bg-surface px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-border-strong focus:outline-none disabled:opacity-50"
          />
          <button
            type="button"
            onClick={send}
            disabled={!draft.trim() || busy === "reply"}
            className="shrink-0 rounded border border-accent bg-accent px-4 py-2 text-sm font-medium text-accent-text transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy === "reply" ? "..." : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}
