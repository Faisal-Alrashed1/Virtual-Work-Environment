"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { useRequireAuth } from "@/lib/auth-context";
import { AGENT_ORDER } from "@/lib/agents";
import { fetchMyExtraAgents, type ExtraAgent } from "@/lib/team";
import { fetchMyProject, type Project } from "@/lib/projects";
import { assignNextTask } from "@/lib/tasks";
import { useAgents, useLocale } from "@/lib/i18n/locale";
import { ThemeToggle } from "@/components/theme-toggle";
import { LocaleToggle } from "@/components/locale-toggle";

// Reworked from a single long scroll into a guided, step-by-step
// walkthrough — same four pieces of content as before (welcome, team,
// project, how-it-works), plus a closing step, each one its own screen
// with Back/Next and a clickable progress tracker. Also no longer
// first-time-only: reachable any time from the board header, so a
// returning graduate can jump straight to whichever step via the
// tracker dots instead of re-reading everything.
type StepId = "welcome" | "team" | "project" | "how" | "ready";
const STEP_IDS: StepId[] = ["welcome", "team", "project", "how", "ready"];

interface HowItWorksItem {
  title: string;
  body: string;
}

export default function OrientationPage() {
  const { user, loading: authLoading } = useRequireAuth();
  const router = useRouter();
  const { t, tRaw } = useLocale();

  const [project, setProject] = useState<Project | null>(null);
  const [extraAgents, setExtraAgents] = useState<ExtraAgent[]>([]);
  const [dataLoading, setDataLoading] = useState(true);
  const [error, setError] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    if (!user) return;
    (async () => {
      const [existing, agents] = await Promise.all([fetchMyProject(), fetchMyExtraAgents()]);
      setExtraAgents(agents);
      if (existing) {
        // Returning graduate, or a first-timer who already has a
        // project from elsewhere — nothing to bootstrap.
        setProject(existing);
        setDataLoading(false);
        return;
      }
      // First time through with no project yet: orientation itself is
      // what triggers it, same call the task board's "ask manager"
      // button makes. weekly_cycle.py's bootstrap is idempotent, so
      // this is safe even if a graduate revisits this page later.
      try {
        await assignNextTask();
        setProject(await fetchMyProject());
      } catch {
        setError(true);
      }
      setDataLoading(false);
    })();
  }, [user]);

  const stepLabels = tRaw<string[]>("orientation.steps");
  const firstName = user?.fullName?.split(" ")[0] || t("orientation.fallbackName");
  const step = STEP_IDS[stepIndex];
  const isFirst = stepIndex === 0;
  const isLast = stepIndex === STEP_IDS.length - 1;

  if (authLoading || !user) {
    return (
      <main className="flex flex-1 items-center justify-center">
        <p className="text-sm text-text-muted">{t("common.loading")}</p>
      </main>
    );
  }

  return (
    <main className="bg-blueprint-grid flex flex-1 justify-center px-6 py-12">
      <div className="w-full max-w-2xl">
        <div className="flex items-center justify-between">
          <Link href="/" className="font-mono text-xs text-text-muted hover:text-text-secondary">
            {t("common.venv")}
          </Link>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => router.push("/board")}
              className="text-xs text-text-muted transition-colors hover:text-text-secondary"
            >
              {t("orientation.skipToBoard")}
            </button>
            <LocaleToggle />
            <ThemeToggle />
          </div>
        </div>

        <StepTracker labels={stepLabels} activeIndex={stepIndex} onSelect={setStepIndex} />

        {dataLoading ? (
          <div className="mt-8 rounded border border-border bg-bg-surface p-8 text-center">
            <p className="text-sm text-text-muted">{t("orientation.settingUp")}</p>
          </div>
        ) : (
          <>
            <div className="mt-8 min-h-[320px]">
              <AnimatePresence mode="wait">
                <motion.div
                  key={step}
                  initial={{ opacity: 0, x: 16 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -16 }}
                  transition={{ duration: 0.25, ease: "easeOut" }}
                >
                  {step === "welcome" && <WelcomeStep firstName={firstName} />}
                  {step === "team" && <TeamStep extraAgents={extraAgents} />}
                  {step === "project" && <ProjectStep project={project} error={error} />}
                  {step === "how" && <HowStep items={tRaw<HowItWorksItem[]>("orientation.howItWorksSteps")} />}
                  {step === "ready" && <ReadyStep firstName={firstName} />}
                </motion.div>
              </AnimatePresence>
            </div>

            <div className="mt-8 flex items-center justify-between">
              <button
                type="button"
                onClick={() => setStepIndex((i) => Math.max(0, i - 1))}
                disabled={isFirst}
                className="rounded border border-border px-4 py-2 text-sm text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
              >
                {t("orientation.back")}
              </button>
              {isLast ? (
                <button
                  type="button"
                  onClick={() => router.push("/board")}
                  className="rounded border border-accent bg-accent px-4 py-2 text-sm font-medium text-accent-text transition-colors hover:bg-accent-strong"
                >
                  {t("orientation.goToBoard")}
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => setStepIndex((i) => Math.min(STEP_IDS.length - 1, i + 1))}
                  className="rounded border border-accent bg-accent px-4 py-2 text-sm font-medium text-accent-text transition-colors hover:bg-accent-strong"
                >
                  {t("orientation.next")}
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </main>
  );
}

// Same connected-timeline shape as the board's week-strip subtask
// dots (filled accent = visited, ringed accent = current, hollow =
// upcoming) so the walkthrough reads as one visual language with the
// rest of the app rather than a bespoke wizard control. Dots are
// clickable — the main way a returning graduate jumps straight to one
// section instead of re-reading the whole thing.
function StepTracker({
  labels,
  activeIndex,
  onSelect,
}: {
  labels: string[];
  activeIndex: number;
  onSelect: (i: number) => void;
}) {
  return (
    <ol className="relative mt-6 flex justify-between">
      <span className="absolute inset-x-0 top-[7px] h-px bg-border" aria-hidden />
      {labels.map((label, i) => {
        const done = i < activeIndex;
        const active = i === activeIndex;
        return (
          <li key={label} className="relative flex min-w-0 flex-1 flex-col items-center px-1 text-center">
            <button
              type="button"
              onClick={() => onSelect(i)}
              className="relative z-10 h-3.5 w-3.5 cursor-pointer rounded-full border-2 bg-bg-surface"
              style={{
                borderColor: done || active ? "var(--accent)" : "var(--border-strong)",
                backgroundColor: done ? "var(--accent)" : "var(--bg-surface)",
              }}
              aria-label={label}
            />
            <span
              className={`mt-2 hidden text-[11px] sm:block ${
                active ? "text-text-primary" : "text-text-muted"
              }`}
            >
              {label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function WelcomeStep({ firstName }: { firstName: string }) {
  const { t } = useLocale();
  return (
    <section>
      <h1 className="text-2xl font-medium text-text-primary">
        {t("orientation.welcomeTitle", { name: firstName })}
      </h1>
      <p className="mt-3 text-sm leading-relaxed text-text-secondary">
        {t("orientation.welcomeBody")}
      </p>
    </section>
  );
}

function TeamStep({ extraAgents }: { extraAgents: ExtraAgent[] }) {
  const { t } = useLocale();
  const agents = useAgents();
  return (
    <section>
      <p className="font-mono text-[11px] text-text-muted">{t("orientation.yourTeamEyebrow")}</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        {AGENT_ORDER.map((id) => {
          const meta = agents[id];
          return (
            <div key={id} className="rounded border border-border bg-bg-surface p-3">
              <div className="flex items-center gap-2">
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: `var(${meta.colorVar})` }}
                />
                <span className="font-medium text-text-primary">{meta.name}</span>
              </div>
              <p className="mt-1.5 text-xs text-text-secondary">{meta.role}</p>
            </div>
          );
        })}
        {extraAgents.map((agent) => (
          <div key={agent.id} className="rounded border border-dashed border-border p-3">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-text-muted" />
                <span className="font-medium text-text-primary">{agent.name}</span>
              </div>
              <span className="rounded-full border border-border px-1.5 py-0.5 font-mono text-[10px] text-text-muted">
                {t("orientation.soonBadge")}
              </span>
            </div>
            <p className="mt-1.5 text-xs text-text-secondary">{agent.description}</p>
          </div>
        ))}
      </div>
      {extraAgents.length > 0 && (
        <p className="mt-3 text-xs text-text-muted">{t("orientation.extrasNote")}</p>
      )}
    </section>
  );
}

function ProjectStep({ project, error }: { project: Project | null; error: boolean }) {
  const { t } = useLocale();
  return (
    <section>
      <p className="font-mono text-[11px] text-text-muted">{t("orientation.yourProjectEyebrow")}</p>
      {error || !project ? (
        <div className="mt-3 rounded border border-border bg-bg-surface p-4">
          <p className="text-sm text-text-secondary">{t("orientation.projectError")}</p>
        </div>
      ) : (
        <div className="mt-3 rounded border border-border-strong bg-bg-surface-raised p-4">
          <h2 className="text-base font-medium text-text-primary">{project.title}</h2>
          <p className="mt-1.5 text-sm leading-relaxed text-text-secondary">
            {project.description}
          </p>
        </div>
      )}
    </section>
  );
}

function HowStep({ items }: { items: HowItWorksItem[] }) {
  const { t } = useLocale();
  return (
    <section>
      <p className="font-mono text-[11px] text-text-muted">{t("orientation.howItWorksEyebrow")}</p>
      <div className="mt-3 flex flex-col gap-2">
        {items.map((s, i) => (
          <div key={s.title} className="rounded border border-border bg-bg-surface p-3">
            <div className="flex items-baseline gap-2">
              <span dir="ltr" className="font-mono text-[11px] text-text-muted">
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className="text-sm font-medium text-text-primary">{s.title}</span>
            </div>
            <p className="mt-1 text-sm leading-relaxed text-text-secondary">{s.body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function ReadyStep({ firstName }: { firstName: string }) {
  const { t } = useLocale();
  return (
    <section>
      <h2 className="text-xl font-medium text-text-primary">
        {t("orientation.readyTitle", { name: firstName })}
      </h2>
      <p className="mt-3 text-sm leading-relaxed text-text-secondary">
        {t("orientation.readyBody")}
      </p>
    </section>
  );
}
