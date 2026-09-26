"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Users,
  ArrowLeft,
  ArrowRight,
  Briefcase,
  AlertCircle,
  Terminal,
  Send,
} from "lucide-react";
import { AGENT_ORDER, type AgentId } from "@/lib/agents";
import { resolveAgentDisplay, useAgents, useLocale } from "@/lib/i18n/locale";
import { fetchMyExtraAgents, type ExtraAgent } from "@/lib/team";
import { useRequireAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";
import {
  fetchConversation,
  fetchTeamConversation,
  sendChatMessage,
  sendTeamMessage,
} from "@/lib/meeting";
import { timeAgo } from "@/lib/format";
import { AccountMenu } from "@/components/nav/account-menu";
import { IconLink } from "@/components/nav/icon-link";
import { ThemeToggle } from "@/components/theme-toggle";
import { LocaleToggle } from "@/components/locale-toggle";

// A sentinel alongside real agent ids (see lib/agents.ts's AgentId) for
// the Team Room — a shared thread with the whole team, not one more
// 1:1 conversation. Kept as a plain string (not part of AgentId) since
// it never reaches the backend as an agent_type.
const TEAM_ROOM_ID = "team";

/** The shape both a 1:1 thread's messages (lib/meeting.ts's ChatMessage)
 * and the Team Room's (TeamMessage) render as — agentType nullable to
 * cover the Team Room's user turns, which a 1:1 thread never has. */
interface DisplayMessage {
  id: string;
  agentType: string | null;
  sender: "user" | "agent";
  content: string;
  createdAt: string;
}

function Dot({
  colorVar,
  className = "h-2 w-2",
}: {
  colorVar: string | null;
  className?: string;
}) {
  return colorVar ? (
    <span
      className={`${className} rounded-full`}
      style={{ backgroundColor: `var(${colorVar})` }}
    />
  ) : (
    <span className={`${className} rounded-full bg-text-muted`} />
  );
}

export default function MeetingPage() {
  const { user, loading: authLoading } = useRequireAuth();
  const { t, locale } = useLocale();
  const agents = useAgents();
  const OPENERS: Record<AgentId, string> = {
    manager: t("meeting.openers.manager"),
    mentor: t("meeting.openers.mentor"),
    hr: t("meeting.openers.hr"),
  };
  const [extraAgents, setExtraAgents] = useState<ExtraAgent[]>([]);
  const [agent, setAgent] = useState<string>("manager");
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [loadingThread, setLoadingThread] = useState(true);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const isTeamRoom = agent === TEAM_ROOM_ID;

  useEffect(() => {
    if (user)
      fetchMyExtraAgents()
        .then(setExtraAgents)
        .catch(() => {});
  }, [user]);

  const loadThread = useCallback(
    async (a: string) => {
      setLoadingThread(true);
      try {
        setMessages(
          a === TEAM_ROOM_ID
            ? await fetchTeamConversation()
            : await fetchConversation(a),
        );
        setError(null);
      } catch (err) {
        setError(
          err instanceof ApiError ? err.message : t("meeting.loadError"),
        );
        setMessages([]);
      } finally {
        setLoadingThread(false);
      }
    },
    [t],
  );

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
    const optimistic: DisplayMessage = {
      id: `temp-${Date.now()}`,
      agentType: null,
      sender: "user",
      content,
      createdAt: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimistic]);
    setSending(true);
    try {
      const reply = isTeamRoom
        ? await sendTeamMessage(content)
        : await sendChatMessage(agent, content);
      setMessages((prev) => [...prev, reply]);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("meeting.sendError"));
      // Roll back the optimistic message on failure.
      setMessages((prev) => prev.filter((m) => m.id !== optimistic.id));
      setDraft(content);
    } finally {
      setSending(false);
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

  const meta = resolveAgentDisplay(agent, agents, extraAgents);
  const opener = agent in agents ? OPENERS[agent as AgentId] : meta.role;
  const allAgentIds = [...AGENT_ORDER, ...extraAgents.map((a) => a.id)];
  const composerName = isTeamRoom ? t("meeting.team.roomName") : meta.name;
  const BackArrow = locale === "ar" ? ArrowRight : ArrowLeft;

  return (
    <main className="grid h-dvh grid-rows-[auto_1fr] bg-bg-base text-text-primary selection:bg-accent selection:text-accent-text">
      {/* Top Engineering Header Bar */}
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
              MEETING_CONSOLE
            </span>
          </Link>

          <div className="hidden items-center gap-2 border-s border-border ps-4 sm:flex">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            <h1 className="font-mono text-xs font-medium uppercase tracking-wider text-text-primary">
              {t("nav.meetingRoomTitle")}
            </h1>
          </div>
        </div>

        {/* Global Toolbar */}
        <div className="flex items-center gap-2">
          <Link
            href="/workspace"
            className="inline-flex h-8 items-center gap-1.5 rounded border border-border bg-bg-base px-3 font-mono text-xs text-text-secondary transition-colors hover:border-border-strong hover:bg-bg-surface hover:text-text-primary"
          >
            <Briefcase className="h-3.5 w-3.5" />
            <span>{t("nav.workspace")}</span>
          </Link>

          <IconLink href="/settings" label={t("nav.settings")}>
            <Terminal className="h-3.5 w-3.5" strokeWidth={1.75} />
          </IconLink>

          <div className="mx-1 h-4 border-s border-border" />

          <AccountMenu email={user.email} />
          <LocaleToggle className="bg-bg-base" />
          <ThemeToggle className="bg-bg-base" />
        </div>
      </header>

      {/* Error Strip */}
      {error && (
        <div className="flex items-center gap-2 border-b border-danger/30 bg-danger/10 px-6 py-2.5 text-xs text-danger">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" />
          <p className="flex-1 font-mono">{error}</p>
        </div>
      )}

      {/* Main Terminal Viewport */}
      <div className="grid min-h-0 grid-cols-1 md:grid-cols-[250px_minmax(0,1fr)]">
        {/* Left Column: Channels & Roster */}
        <div className="flex gap-2 overflow-x-auto border-b border-border bg-bg-surface/50 p-3 md:flex-col md:overflow-y-auto md:border-b-0 md:border-e">
          <div className="hidden px-2 pb-1.5 font-mono text-[10px] uppercase tracking-wider text-text-muted md:block">
            CHANNELS // TEAM_MESH
          </div>

          {/* Team Room Button */}
          <button
            type="button"
            onClick={() => setAgent(TEAM_ROOM_ID)}
            className={`group relative flex shrink-0 flex-col items-start rounded border px-3 py-2.5 text-start transition-colors md:shrink ${
              isTeamRoom
                ? "border-accent bg-bg-surface shadow-xs"
                : "border-border bg-bg-surface/40 hover:border-border-strong hover:bg-bg-surface"
            }`}
          >
            {isTeamRoom && (
              <span className="absolute inset-y-0 start-0 w-[2px] bg-accent" />
            )}
            <span className="flex items-center gap-2">
              <Users className="h-3.5 w-3.5 text-text-secondary transition-colors group-hover:text-text-primary" />
              <span className="font-mono text-xs font-medium text-text-primary">
                {t("meeting.team.roomName")}
              </span>
            </span>
            <span className="mt-1 hidden text-[11px] leading-tight text-text-secondary md:block">
              {t("meeting.team.roomTagline")}
            </span>
          </button>

          <div className="mx-1 my-1 hidden border-t border-border md:block" />

          <div className="hidden px-2 pb-1 font-mono text-[10px] uppercase tracking-wider text-text-muted md:block">
            DIRECT_CONSULTATION
          </div>

          {/* 1:1 Agent Selectors */}
          {allAgentIds.map((id) => {
            const m = resolveAgentDisplay(id, agents, extraAgents);
            const active = id === agent;
            return (
              <button
                key={id}
                type="button"
                onClick={() => setAgent(id)}
                className={`group relative flex shrink-0 flex-col items-start rounded border px-3 py-2 text-start transition-colors md:shrink ${
                  active
                    ? "border-accent bg-bg-surface shadow-xs"
                    : "border-border bg-bg-surface/40 hover:border-border-strong hover:bg-bg-surface"
                }`}
              >
                {active && (
                  <span
                    className="absolute inset-y-0 start-0 w-[2px]"
                    style={{
                      backgroundColor: m.colorVar
                        ? `var(${m.colorVar})`
                        : "var(--accent)",
                    }}
                  />
                )}
                <span className="flex items-center gap-2">
                  <Dot colorVar={m.colorVar} />
                  <span className="text-xs font-medium text-text-primary">
                    {m.name}
                  </span>
                </span>
                <span className="mt-0.5 hidden font-mono text-[10px] text-text-muted md:block">
                  {m.role}
                </span>
              </button>
            );
          })}
        </div>

        {/* Right Column: Active Conversation Session */}
        <div className="flex min-h-0 flex-col bg-bg-base">
          {/* Active Consultation Status Bar */}
          <div className="flex h-10 shrink-0 items-center justify-between border-b border-border bg-bg-surface px-6 font-mono text-[10px] text-text-muted">
            <div className="flex items-center gap-2">
              <Dot colorVar={isTeamRoom ? null : meta.colorVar} />
              <span className="uppercase text-text-primary">
                {composerName}
              </span>
              <span className="text-border-strong">|</span>
              <span className="hidden sm:inline">
                {isTeamRoom ? "SHARED_BROADCAST" : meta.role}
              </span>
            </div>
            <span className="hidden sm:inline">STATE: READY_FOR_INPUT</span>
          </div>

          {/* Conversation Stream */}
          <div
            ref={scrollRef}
            className="thin-scrollbar relative min-h-0 flex-1 overflow-y-auto px-6 py-6"
          >
            {/* Background grid texture */}
            <div className="pointer-events-none absolute inset-0 bg-blueprint-grid opacity-20" />

            {loadingThread ? (
              <div className="flex h-full items-center justify-center">
                <div className="flex items-center gap-2 rounded border border-border bg-bg-surface px-4 py-2 font-mono text-xs text-text-muted">
                  <span className="h-1.5 w-1.5 animate-ping rounded-full bg-accent" />
                  <span>{t("common.loading")}</span>
                </div>
              </div>
            ) : messages.length === 0 ? (
              <div className="relative mx-auto max-w-md pt-12 text-center">
                <div className="relative rounded border border-border bg-bg-surface p-8">
                  {/* Corner marks */}
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

                  {isTeamRoom ? (
                    <span className="mx-auto flex h-10 w-10 items-center justify-center rounded-full border border-border bg-bg-base text-accent-ink">
                      <Users className="h-4 w-4" />
                    </span>
                  ) : (
                    <span
                      className="mx-auto flex h-10 w-10 items-center justify-center rounded-full border border-border bg-bg-base"
                      style={
                        meta.colorVar
                          ? { borderColor: `var(${meta.colorVar})` }
                          : undefined
                      }
                    >
                      <Dot colorVar={meta.colorVar} className="h-3 w-3" />
                    </span>
                  )}

                  <h2 className="mt-4 font-mono text-xs font-semibold uppercase tracking-wider text-text-primary">
                    {isTeamRoom
                      ? t("meeting.team.emptyTitle")
                      : t("meeting.meetWith", { name: meta.name })}
                  </h2>
                  <p className="mt-2 text-xs leading-relaxed text-text-secondary">
                    {isTeamRoom ? t("meeting.team.emptyBody") : opener}
                  </p>
                </div>
              </div>
            ) : (
              <div className="relative mx-auto flex max-w-2xl flex-col gap-3">
                {messages.map((m) => {
                  const isUser = m.sender === "user";
                  const speaker = m.agentType
                    ? resolveAgentDisplay(m.agentType, agents, extraAgents)
                    : null;
                  return (
                    <motion.div
                      key={m.id}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.15 }}
                      className={`max-w-[85%] rounded border p-3 ${
                        isUser
                          ? "self-end border-accent/40 bg-accent/10"
                          : "self-start border-border bg-bg-surface"
                      }`}
                    >
                      <div className="flex items-center gap-1.5 border-b border-border/40 pb-1.5">
                        {!isUser && (
                          <Dot
                            colorVar={speaker?.colorVar ?? null}
                            className="h-1.5 w-1.5"
                          />
                        )}
                        <span className="font-mono text-[10px] text-text-muted">
                          {isUser
                            ? t("common.you")
                            : (speaker?.name ?? meta.name)}
                        </span>
                        <span className="font-mono text-[9px] text-text-muted">
                          {timeAgo(m.createdAt)}
                        </span>
                      </div>
                      <p className="mt-2 whitespace-pre-line text-xs leading-relaxed text-text-primary">
                        {m.content}
                      </p>
                    </motion.div>
                  );
                })}
                {sending && (
                  <div className="max-w-[80%] self-start rounded border border-dashed border-border bg-bg-surface/50 px-3.5 py-2">
                    <p className="flex items-center gap-2 font-mono text-[11px] text-text-muted">
                      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
                      <span>
                        {isTeamRoom
                          ? t("meeting.team.typing")
                          : t("meeting.typing", { name: meta.name })}
                      </span>
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Interactive Dispatch Terminal */}
          <div className="border-t border-border bg-bg-surface/90 p-4 backdrop-blur-xs">
            <div className="mx-auto flex max-w-2xl flex-col gap-2">
              <div className="relative">
                <textarea
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      send();
                    }
                  }}
                  rows={3}
                  placeholder={t("meeting.messagePlaceholder", {
                    name: composerName,
                  })}
                  disabled={sending}
                  className="thin-scrollbar min-h-[70px] w-full resize-none rounded border border-border bg-bg-surface-raised p-3 text-xs text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none disabled:opacity-50"
                />
              </div>

              <div className="flex items-center justify-between">
                <span className="hidden font-mono text-[10px] text-text-muted sm:inline">
                  PRESS [ENTER] TO DISPATCH // [SHIFT + ENTER] FOR NEW LINE
                </span>
                <button
                  type="button"
                  onClick={send}
                  disabled={!draft.trim() || sending}
                  className="ms-auto inline-flex h-8 items-center gap-1.5 rounded border border-accent bg-accent px-4 font-mono text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <Send className="h-3 w-3" />
                  <span>
                    {sending ? t("common.sendBusy") : t("common.send")}
                  </span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
