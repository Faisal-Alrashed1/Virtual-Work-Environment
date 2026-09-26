"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Bell,
  Compass,
  Settings as SettingsIcon,
  Layers,
  ArrowUpRight,
  Activity,
  Terminal,
} from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { fetchTasks, type Task } from "@/lib/tasks";
import { fetchMyProject, currentWeek, type Project } from "@/lib/projects";
import { fetchDashboard, type Dashboard } from "@/lib/dashboard";
import { fetchMyReviews, type Review } from "@/lib/reviews";
import { fetchMyExtraAgents, type ExtraAgent } from "@/lib/team";
import { fetchMyInvitations } from "@/lib/invitations";
import {
  DetailPanel,
  type BoardSelection,
} from "@/components/board/detail-panel";
import { FocusHero } from "@/components/dashboard/focus-hero";
import { WeekStrip } from "@/components/dashboard/week-strip";
import { StatRow } from "@/components/dashboard/stat-row";
import { AgentCards } from "@/components/dashboard/agent-cards";
import { FlowSection } from "@/components/dashboard/flow-section";
import { AccountMenu } from "@/components/nav/account-menu";
import { IconLink } from "@/components/nav/icon-link";
import { useLocale } from "@/lib/i18n/locale";
import { ThemeToggle } from "@/components/theme-toggle";
import { LocaleToggle } from "@/components/locale-toggle";

// The one task the graduate should act on now: the most recent
// non-reviewed task (todo/in_progress/submitted). Mirrors the backend's
// "one subtask at a time" rule — there's normally at most one open.
function focusTask(tasks: Task[]): Task | null {
  const open = tasks.filter((t) => t.status !== "reviewed");
  if (open.length === 0) return null;
  return open.reduce((latest, t) =>
    new Date(t.createdAt) > new Date(latest.createdAt) ? t : latest,
  );
}

export default function BoardPage() {
  const { user, loading } = useRequireAuth();
  const { t } = useLocale();
  const [selection, setSelection] = useState<BoardSelection>(null);

  const [tasks, setTasks] = useState<Task[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [extraAgents, setExtraAgents] = useState<ExtraAgent[]>([]);
  const [pendingInvitations, setPendingInvitations] = useState(0);
  const [dataLoading, setDataLoading] = useState(true);

  useEffect(() => {
    if (!user) return;
    Promise.allSettled([
      fetchTasks(),
      fetchMyProject(),
      fetchDashboard(),
      fetchMyReviews(),
      fetchMyExtraAgents(),
      fetchMyInvitations(),
    ])
      .then(([t, p, d, r, a, inv]) => {
        if (t.status === "fulfilled") setTasks(t.value);
        if (p.status === "fulfilled") setProject(p.value);
        if (d.status === "fulfilled") setDashboard(d.value);
        if (r.status === "fulfilled") setReviews(r.value);
        if (a.status === "fulfilled") setExtraAgents(a.value);
        if (inv.status === "fulfilled") {
          setPendingInvitations(
            inv.value.filter((i) => i.status === "pending").length,
          );
        }
      })
      .finally(() => setDataLoading(false));
  }, [user]);

  const week = project ? currentWeek(project) : null;
  const focus = focusTask(tasks);
  const firstName =
    user?.fullName?.split(" ")[0] || t("orientation.fallbackName");

  if (loading || !user) {
    return (
      <main className="flex min-h-screen flex-1 items-center justify-center bg-bg-base">
        <div className="flex items-center gap-2 rounded border border-border bg-bg-surface px-4 py-3 font-mono text-xs text-text-muted">
          <span className="h-2 w-2 animate-ping rounded-full bg-accent" />
          <span>{t("common.loading")}</span>
        </div>
      </main>
    );
  }

  return (
    <main className="grid h-dvh grid-rows-[auto_1fr] bg-bg-base text-text-primary selection:bg-accent selection:text-accent-text">
      {/* Top Architecture Bar */}
      <header className="z-20 flex h-14 items-center justify-between border-b border-border bg-bg-surface/90 px-6 backdrop-blur-md">
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="group flex items-center gap-2 font-mono text-xs text-text-muted transition-colors hover:text-text-primary"
          >
            <span className="font-semibold text-text-primary">
              {t("common.venv")}
            </span>
            <span className="text-border-strong">/</span>
            <span className="text-[10px] text-text-muted transition-colors group-hover:text-text-secondary">
              ENGINEERING_FLOOR
            </span>
          </Link>

          <div className="hidden items-center gap-2 border-s border-border ps-4 sm:flex">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
              {t("nav.homeBoardTitle")}
            </span>
          </div>
        </div>

        {/* Global Action Cluster */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2">
            <Link
              href="/workspace"
              className="inline-flex h-8 items-center gap-1.5 rounded border border-accent bg-accent px-3.5 font-mono text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong"
            >
              <span>{t("nav.workspace")}</span>
              <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
            <Link
              href="/meeting"
              className="inline-flex h-8 items-center rounded border border-border bg-bg-base px-3 font-mono text-xs text-text-secondary transition-colors hover:border-border-strong hover:bg-bg-surface hover:text-text-primary"
            >
              {t("nav.meetingRoom")}
            </Link>
          </div>

          <div className="mx-1 h-4 border-s border-border" />

          {/* System Utility Cluster */}
          <div className="flex items-center gap-1.5">
            <IconLink href="/orientation" label={t("nav.howItWorks")}>
              <Compass className="h-3.5 w-3.5" strokeWidth={1.75} />
            </IconLink>
            <IconLink href="/settings" label={t("nav.settings")}>
              <SettingsIcon className="h-3.5 w-3.5" strokeWidth={1.75} />
            </IconLink>
            <IconLink
              href="/invitations"
              label={t("invitations.title")}
              badge={pendingInvitations}
            >
              <Bell className="h-3.5 w-3.5" strokeWidth={1.75} />
            </IconLink>
          </div>

          <div className="mx-1 h-4 border-s border-border" />

          <AccountMenu email={user.email} />
          <LocaleToggle className="bg-bg-base" />
          <ThemeToggle className="bg-bg-base" />
        </div>
      </header>

      {/* Main Blueprint Dual Panel */}
      <div className="grid min-h-0 grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        {/* Left Column: Dashboard Stream */}
        <div className="overlay-scrollbar relative min-h-0 overflow-y-auto border-b border-border lg:border-b-0 lg:border-e">
          {/* Subtle Technical Grid Overlay on Stream */}
          <div className="pointer-events-none absolute inset-0 bg-blueprint-grid opacity-30" />

          <div className="relative flex flex-col gap-6 px-6 py-6 sm:px-8">
            {/* Engineer Profile Banner */}
            <div className="relative rounded border border-border bg-bg-surface p-5">
              <span className="absolute inset-x-0 top-0 h-[2px] bg-accent" />
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
                <div className="flex items-center gap-2">
                  <Terminal className="h-3.5 w-3.5 text-accent-ink" />
                  <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                    ENGINEER_LOG // ACTIVE_SESSION
                  </span>
                </div>
                <span className="font-mono text-[10px] text-text-muted">
                  SYS.ID: {user.id ? `UID_${user.id}` : "ACTIVE_OPERATOR"}
                </span>
              </div>

              <div className="mt-3 flex items-baseline justify-between">
                <div>
                  <p className="font-mono text-[11px] text-text-secondary">
                    {t("board.welcomeBack")}
                  </p>
                  <h2 className="mt-0.5 text-2xl font-medium tracking-tight text-text-primary">
                    {firstName}
                  </h2>
                </div>

                <div className="text-end">
                  <span className="inline-flex items-center gap-1.5 rounded border border-border bg-bg-base px-2 py-0.5 font-mono text-[10px] text-text-secondary">
                    <Activity className="h-2.5 w-2.5 text-agent-mentor" />
                    STATUS: ENGAGED
                  </span>
                </div>
              </div>
            </div>

            {/* Dashboard Content */}
            {dataLoading ? (
              <div className="relative rounded border border-dashed border-border bg-bg-surface p-12 text-center">
                <p className="font-mono text-xs text-text-muted">
                  {t("board.loadingWorkspace")}
                </p>
              </div>
            ) : (
              <>
                <FocusHero
                  task={focus}
                  week={week}
                  hasProject={dashboard?.hasActiveProject ?? project !== null}
                />
                {dashboard && <StatRow dashboard={dashboard} />}
                <WeekStrip week={week} projectTitle={project?.title ?? null} />
                {dashboard && (
                  <div className="relative rounded border border-border bg-bg-surface p-5">
                    <div className="mb-4 flex items-center justify-between border-b border-border pb-2.5">
                      <div className="flex items-center gap-2">
                        <Layers className="h-3.5 w-3.5 text-accent-ink" />
                        <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                          {t("board.yourTeam")}
                        </span>
                      </div>
                      <span className="font-mono text-[10px] text-text-muted">
                        ROSTER_COUNT: {3 + extraAgents.length}
                      </span>
                    </div>
                    <AgentCards
                      dashboard={dashboard}
                      reviews={reviews}
                      extraAgents={extraAgents}
                    />
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Right Column: Floor-plan Interactive Agent Mesh Canvas */}
        <div className="relative flex h-[60vh] min-h-0 flex-col bg-bg-base lg:h-auto">
          {/* Canvas Sub-header */}
          <div className="flex h-10 shrink-0 items-center justify-between border-b border-border bg-bg-surface px-4 font-mono text-[10px] text-text-muted">
            <span className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
              TOPOLOGY // AGENT_COMMUNICATION_MESH
            </span>
            <span className="hidden sm:inline">INTERACTION_MODE: EXPLORE</span>
          </div>

          {/* Interactive React Flow Canvas */}
          <div className="relative flex-1">
            <FlowSection onSelect={setSelection} extraAgents={extraAgents} />
          </div>

          {/* Bottom Canvas Telemetry Strip */}
          <div className="flex h-8 shrink-0 items-center justify-between border-t border-border bg-bg-surface px-4 font-mono text-[9px] text-text-muted">
            <span>GRID: 32PX // PROJECTION: SCHEMATIC</span>
            <span>SYSTEM_CLEARANCE: LEVEL_1</span>
          </div>
        </div>
      </div>

      {/* Flyout Inspector Drawer */}
      <DetailPanel
        selection={selection}
        hasCv={user.hasCv}
        reviewedTaskId={tasks.find((t) => t.status === "reviewed")?.id ?? null}
        week={week}
        projectTitle={project?.title ?? null}
        extraAgents={extraAgents}
        onClose={() => setSelection(null)}
      />
    </main>
  );
}
