"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { AGENTS, AGENT_ORDER, type AgentId } from "@/lib/agents";
import { agentDisplay } from "@/lib/agent-display";
import { fetchMyExtraAgents, type ExtraAgent } from "@/lib/team";
import { useRequireAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";
import {
  fetchConversation,
  sendChatMessage,
  type ChatMessage,
} from "@/lib/meeting";
import { timeAgo } from "@/lib/format";

const OPENERS: Record<AgentId, string> = {
  manager: "Ask about your project, this week's plan, or what to prioritize.",
  mentor: "Ask for code advice, review feedback, or how to level up.",
  hr: "Ask about your growth, strengths, or where to focus next.",
};

function Dot({ colorVar, className = "h-2 w-2" }: { colorVar: string | null; className?: string }) {
  return colorVar ? (
    <span className={`${className} rounded-full`} style={{ backgroundColor: `var(${colorVar})` }} />
  ) : (
    <span className={`${className} rounded-full bg-text-muted`} />
  );
}

export default function MeetingPage() {
  const { user, loading: authLoading } = useRequireAuth();
  const [extraAgents, setExtraAgents] = useState<ExtraAgent[]>([]);
  const [agent, setAgent] = useState<string>("manager");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loadingThread, setLoadingThread] = useState(true);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (user) fetchMyExtraAgents().then(setExtraAgents).catch(() => {});
  }, [user]);

  const loadThread = useCallback(async (a: string) => {
    setLoadingThread(true);
    try {
      setMessages(await fetchConversation(a));
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load the conversation.");
      setMessages([]);
    } finally {
      setLoadingThread(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (user) loadThread(agent);
  }, [user, agent, loadThread]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length, sending]);

  async function send() {
    const content = draft.trim();
    if (!content || sending) return;
    setDraft("");
    // Optimistic: show the user's message immediately with a temp id.
    const optimistic: ChatMessage = {
      id: `temp-${Date.now()}`,
      agentType: agent,
      sender: "user",
      content,
      createdAt: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimistic]);
    setSending(true);
    try {
      const reply = await sendChatMessage(agent, content);
      setMessages((prev) => [...prev, reply]);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't send that message.");
      // Roll back the optimistic message on failure.
      setMessages((prev) => prev.filter((m) => m.id !== optimistic.id));
      setDraft(content);
    } finally {
      setSending(false);
    }
  }

  if (authLoading || !user) {
    return (
      <main className="flex flex-1 items-center justify-center">
        <p className="text-sm text-text-muted">Loading...</p>
      </main>
    );
  }

  const meta = agentDisplay(agent, extraAgents);
  const opener = agent in AGENTS ? OPENERS[agent as AgentId] : meta.role;
  const allAgentIds = [...AGENT_ORDER, ...extraAgents.map((a) => a.id)];

  return (
    <main className="grid h-dvh grid-rows-[auto_1fr]">
      <header className="flex items-center justify-between border-b border-border px-6 py-4">
        <div>
          <Link
            href="/board"
            className="font-mono text-xs text-text-muted hover:text-text-secondary"
          >
            venv / board
          </Link>
          <h1 className="mt-1 text-lg font-medium text-text-primary">
            Meeting room
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/workspace"
            className="rounded border border-border px-3 py-1.5 text-xs text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
          >
            Workspace
          </Link>
          <Link
            href="/logout"
            className="rounded border border-border px-3 py-1 text-xs text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
          >
            Log out
          </Link>
        </div>
      </header>

      {error && (
        <div className="border-b border-border bg-bg-surface px-6 py-2">
          <p className="text-sm text-danger">{error}</p>
        </div>
      )}

      {/* Agent picker rail | conversation. On mobile the picker becomes a
          horizontal strip up top. */}
      <div className="grid min-h-0 grid-cols-1 md:grid-cols-[220px_minmax(0,1fr)]">
        <div className="flex gap-2 overflow-x-auto border-b border-border p-3 md:flex-col md:overflow-visible md:border-b-0 md:border-r">
          {allAgentIds.map((id) => {
            const m = agentDisplay(id, extraAgents);
            const active = id === agent;
            return (
              <button
                key={id}
                type="button"
                onClick={() => setAgent(id)}
                className={`flex shrink-0 flex-col items-start rounded border px-3 py-2.5 text-left transition-colors md:shrink ${
                  active
                    ? "border-accent bg-bg-surface"
                    : "border-border hover:border-border-strong"
                }`}
              >
                <span className="flex items-center gap-2">
                  <Dot colorVar={m.colorVar} />
                  <span className="text-sm font-medium text-text-primary">
                    {m.name}
                  </span>
                </span>
                <span className="mt-0.5 hidden text-xs text-text-secondary md:block">
                  {m.role}
                </span>
              </button>
            );
          })}
        </div>

        <div className="flex min-h-0 flex-col">
          <div
            ref={scrollRef}
            className="thin-scrollbar min-h-0 flex-1 overflow-y-auto px-6 py-6"
          >
            {loadingThread ? (
              <p className="text-center text-sm text-text-muted">Loading...</p>
            ) : messages.length === 0 ? (
              <div className="mx-auto max-w-md pt-10 text-center">
                <span
                  className="mx-auto flex h-10 w-10 items-center justify-center rounded-full"
                  style={
                    meta.colorVar
                      ? { backgroundColor: `color-mix(in srgb, var(${meta.colorVar}) 20%, transparent)` }
                      : { backgroundColor: "color-mix(in srgb, var(--text-muted) 20%, transparent)" }
                  }
                >
                  <Dot colorVar={meta.colorVar} className="h-2.5 w-2.5" />
                </span>
                <h2 className="mt-3 text-lg font-medium text-text-primary">
                  Meet with {meta.name}
                </h2>
                <p className="mt-1 text-sm text-text-secondary">{opener}</p>
              </div>
            ) : (
              <div className="mx-auto flex max-w-2xl flex-col gap-3">
                {messages.map((m) => {
                  const isUser = m.sender === "user";
                  return (
                    <motion.div
                      key={m.id}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.2 }}
                      className={`max-w-[80%] rounded border px-3.5 py-2.5 ${
                        isUser
                          ? "self-end border-accent/40 bg-accent/10"
                          : "self-start border-border bg-bg-surface"
                      }`}
                    >
                      <div className="flex items-center gap-1.5">
                        {!isUser && <Dot colorVar={meta.colorVar} className="h-1.5 w-1.5" />}
                        <span className="font-mono text-[10px] text-text-muted">
                          {isUser ? "You" : meta.name} · {timeAgo(m.createdAt)}
                        </span>
                      </div>
                      <p className="mt-1 whitespace-pre-line text-sm text-text-primary">
                        {m.content}
                      </p>
                    </motion.div>
                  );
                })}
                {sending && (
                  <div className="max-w-[80%] self-start rounded border border-dashed border-border px-3.5 py-2.5">
                    <p className="font-mono text-[11px] text-text-muted">
                      {meta.name} is typing...
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="border-t border-border p-3">
            <div className="mx-auto flex max-w-2xl items-end gap-2">
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
                placeholder={`Message ${meta.name}... (Enter to send)`}
                disabled={sending}
                className="thin-scrollbar min-h-0 flex-1 resize-none rounded border border-border bg-bg-surface px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-border-strong focus:outline-none disabled:opacity-50"
              />
              <button
                type="button"
                onClick={send}
                disabled={!draft.trim() || sending}
                className="shrink-0 rounded border border-accent bg-accent px-5 py-2 text-sm font-medium text-accent-text transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-40"
              >
                {sending ? "..." : "Send"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
