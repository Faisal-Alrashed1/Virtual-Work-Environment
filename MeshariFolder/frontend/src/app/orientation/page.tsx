"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowLeft,
  ArrowRight,
  Compass,
  CheckCircle2,
  FolderGit2,
  ArrowUpRight,
} from "lucide-react";
import { useRequireAuth } from "@/lib/auth-context";
import { AGENT_ORDER } from "@/lib/agents";
import { fetchMyExtraAgents, type ExtraAgent } from "@/lib/team";
import { fetchMyProject, type Project } from "@/lib/projects";
import { assignNextTask } from "@/lib/tasks";
import { useAgents, useLocale } from "@/lib/i18n/locale";
import { ThemeToggle } from "@/components/theme-toggle";
import { LocaleToggle } from "@/components/locale-toggle";

type StepId = "welcome" | "team" | "project" | "how" | "ready";
const STEP_IDS: StepId[] = ["welcome", "team", "project", "how", "ready"];

interface HowItWorksItem {
  title: string;
  body: string;
}

export default function OrientationPage() {
  const { user, loading: authLoading } = useRequireAuth();
  const router = useRouter();
  const { t, tRaw, locale } = useLocale();

  const [project, setProject] = useState<Project | null>(null);
  const [extraAgents, setExtraAgents] = useState<ExtraAgent[]>([]);
  const [dataLoading, setDataLoading] = useState(true);
  const [error, setError] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    if (!user) return;
    (async () => {
      const [existing, agents] = await Promise.all([
        fetchMyProject(),
        fetchMyExtraAgents(),
      ]);
      setExtraAgents(agents);
      if (existing) {
        setProject(existing);
        setDataLoading(false);
        return;
      }
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
  const firstName =
    user?.fullName?.split(" ")[0] || t("orientation.fallbackName");
  const step = STEP_IDS[stepIndex];
  const isFirst = stepIndex === 0;
  const isLast = stepIndex === STEP_IDS.length - 1;

  const BackArrow = locale === "ar" ? ArrowRight : ArrowLeft;
  const NextArrow = locale === "ar" ? ArrowLeft : ArrowRight;

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

  // Flip slide direction according to reading flow
  const slideDirection = locale === "ar" ? -16 : 16;

  return (
    <main className="relative flex min-h-screen flex-1 flex-col items-center justify-center bg-blueprint-grid px-6 py-16 text-text-primary selection:bg-accent selection:text-accent-text">
      {/* Top Engineering Header */}
      <header className="fixed inset-x-0 top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-bg-base/80 px-6 backdrop-blur-md">
        <Link
          href="/"
          className="group flex items-center gap-2 font-mono text-xs text-text-muted transition-colors hover:text-text-primary"
        >
          <BackArrow className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5 rtl:group-hover:translate-x-0.5" />
          <span>{t("common.venv")}</span>
          <span className="hidden text-border-strong sm:inline">/</span>
          <span className="hidden text-[10px] text-text-muted sm:inline">
            SYS.INDUCTION
          </span>
        </Link>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => router.push("/board")}
            className="flex items-center gap-1 font-mono text-xs text-text-muted transition-colors hover:text-text-primary"
          >
            <span>{t("orientation.skipToBoard")}</span>
            <ArrowUpRight className="h-3 w-3" />
          </button>
          <div className="mx-1 h-4 border-s border-border" />
          <LocaleToggle className="bg-bg-surface" />
          <ThemeToggle className="bg-bg-surface" />
        </div>
      </header>

      {/* Main Induction Walkthrough Console */}
      <div className="w-full max-w-2xl">
        <div className="relative rounded border border-border bg-bg-surface p-6 sm:p-8">
          {/* Technical Corner Markers */}
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

          {/* Top hairline indicator */}
          <span className="absolute inset-x-0 top-0 h-[2px] bg-accent" />

          {/* Protocol Header */}
          <div className="flex items-center justify-between border-b border-border pb-4">
            <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-text-muted">
              <Compass className="h-3.5 w-3.5 text-accent-ink" />
              <span>ORIENTATION_PROTOCOL</span>
            </div>
            <span className="font-mono text-[10px] text-text-muted">
              STEP 0{stepIndex + 1} 0{STEP_IDS.length}
            </span>
          </div>

          {/* Step Timeline Tracker */}
          <StepTracker
            labels={stepLabels}
            activeIndex={stepIndex}
            onSelect={setStepIndex}
          />

          {dataLoading ? (
            <div className="mt-8 flex h-52 items-center justify-center rounded border border-dashed border-border bg-bg-surface-raised/40">
              <div className="flex items-center gap-2 font-mono text-xs text-text-muted">
                <span className="h-1.5 w-1.5 animate-ping rounded-full bg-accent" />
                <span>{t("orientation.settingUp")}</span>
              </div>
            </div>
          ) : (
            <>
              {/* Dynamic Content Viewport */}
              <div className="mt-8 min-h-[300px]">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={step}
                    initial={{ opacity: 0, x: slideDirection }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -slideDirection }}
                    transition={{ duration: 0.2, ease: "easeOut" }}
                  >
                    {step === "welcome" && (
                      <WelcomeStep firstName={firstName} />
                    )}
                    {step === "team" && <TeamStep extraAgents={extraAgents} />}
                    {step === "project" && (
                      <ProjectStep project={project} error={error} />
                    )}
                    {step === "how" && (
                      <HowStep
                        items={tRaw<HowItWorksItem[]>(
                          "orientation.howItWorksSteps",
                        )}
                      />
                    )}
                    {step === "ready" && <ReadyStep firstName={firstName} />}
                  </motion.div>
                </AnimatePresence>
              </div>

              {/* Navigation Actions Footer */}
              <div className="mt-8 flex items-center justify-between border-t border-border pt-5">
                <button
                  type="button"
                  onClick={() => setStepIndex((i) => Math.max(0, i - 1))}
                  disabled={isFirst}
                  className="inline-flex h-9 items-center gap-1.5 rounded border border-border bg-bg-base px-4 font-mono text-xs text-text-secondary transition-colors hover:border-border-strong hover:bg-bg-surface-raised hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <BackArrow className="h-3 w-3" />
                  <span>{t("orientation.back")}</span>
                </button>

                {isLast ? (
                  <button
                    type="button"
                    onClick={() => router.push("/board")}
                    className="inline-flex h-9 items-center gap-1.5 rounded border border-accent bg-accent px-5 font-mono text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong"
                  >
                    <span>{t("orientation.goToBoard")}</span>
                    <ArrowUpRight className="h-3.5 w-3.5" />
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() =>
                      setStepIndex((i) => Math.min(STEP_IDS.length - 1, i + 1))
                    }
                    className="inline-flex h-9 items-center gap-1.5 rounded border border-accent bg-accent px-5 font-mono text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong"
                  >
                    <span>{t("orientation.next")}</span>
                    <NextArrow className="h-3 w-3" />
                  </button>
                )}
              </div>
            </>
          )}
        </div>

        {/* Console Telemetry Footer */}
        <div className="mt-6 flex items-center justify-between px-2 font-mono text-[10px] text-text-muted">
          <span>ONBOARDING_WALKTHROUGH</span>
          <span>EST_TIME: ~2 MIN</span>
        </div>
      </div>
    </main>
  );
}

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
      <span
        className="absolute inset-x-0 top-[7px] h-px bg-border"
        aria-hidden
      />
      {labels.map((label, i) => {
        const done = i < activeIndex;
        const active = i === activeIndex;
        return (
          <li
            key={label}
            className="relative flex min-w-0 flex-1 flex-col items-center px-1 text-center"
          >
            <button
              type="button"
              onClick={() => onSelect(i)}
              className="relative z-10 flex h-3.5 w-3.5 cursor-pointer items-center justify-center rounded-full border-2 transition-all hover:scale-110"
              style={{
                borderColor:
                  done || active ? "var(--accent)" : "var(--border-strong)",
                backgroundColor: done ? "var(--accent)" : "var(--bg-surface)",
              }}
              aria-label={label}
            >
              {done && <span className="h-1 w-1 rounded-full bg-accent-text" />}
            </button>
            <span
              className={`mt-2 hidden font-mono text-[10px] uppercase tracking-wider sm:block ${
                active ? "font-medium text-text-primary" : "text-text-muted"
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
    <section className="flex flex-col justify-center">
      <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
        PHASE_01 // GREETING
      </span>
      <h1 className="mt-2 text-2xl font-medium tracking-tight text-text-primary sm:text-3xl">
        {t("orientation.welcomeTitle", { name: firstName })}
      </h1>
      <p className="mt-4 text-sm leading-relaxed text-text-secondary sm:text-base">
        {t("orientation.welcomeBody")}
      </p>
      <div className="mt-6 rounded border border-border bg-bg-surface-raised/40 p-4">
        <p className="font-mono text-xs text-text-muted">
          {t("orientation.welcomeNote")}
        </p>
      </div>
    </section>
  );
}

function TeamStep({ extraAgents }: { extraAgents: ExtraAgent[] }) {
  const { t } = useLocale();
  const agents = useAgents();
  return (
    <section>
      <div className="flex items-center justify-between border-b border-border pb-2">
        <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
          {t("orientation.yourTeamEyebrow")}
        </span>
        <span className="font-mono text-[10px] text-text-muted">
          CORE + SPECIALISTS
        </span>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {AGENT_ORDER.map((id) => {
          const meta = agents[id];
          return (
            <div
              key={id}
              className="relative flex flex-col justify-between rounded border border-border bg-bg-surface-raised p-3.5 transition-colors hover:border-border-strong"
            >
              <span
                className="absolute inset-x-0 top-0 h-[2px]"
                style={{ backgroundColor: `var(${meta.colorVar})` }}
              />
              <div>
                <div className="flex items-center gap-2">
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ backgroundColor: `var(${meta.colorVar})` }}
                  />
                  <span className="text-xs font-medium text-text-primary">
                    {meta.name}
                  </span>
                </div>
                <p className="mt-1 font-mono text-[10px] text-text-muted">
                  {meta.role}
                </p>
              </div>
            </div>
          );
        })}

        {extraAgents.map((agent) => (
          <div
            key={agent.id}
            className="relative flex flex-col justify-between rounded border border-dashed border-border bg-bg-base/50 p-3.5"
          >
            <div>
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-text-muted" />
                  <span className="text-xs font-medium text-text-primary">
                    {agent.name}
                  </span>
                </div>
                <span className="rounded border border-border px-1.5 py-0.2 font-mono text-[9px] uppercase text-text-muted">
                  {t("orientation.soonBadge")}
                </span>
              </div>
              <p className="mt-2 text-[11px] leading-relaxed text-text-secondary">
                {agent.description}
              </p>
            </div>
          </div>
        ))}
      </div>

      {extraAgents.length > 0 && (
        <p className="mt-4 font-mono text-[11px] text-text-muted">
          {t("orientation.extrasNote")}
        </p>
      )}
    </section>
  );
}

function ProjectStep({
  project,
  error,
}: {
  project: Project | null;
  error: boolean;
}) {
  const { t } = useLocale();
  return (
    <section>
      <div className="flex items-center justify-between border-b border-border pb-2">
        <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
          {t("orientation.yourProjectEyebrow")}
        </span>
        <span className="font-mono text-[10px] text-text-muted">
          PROJECT_SECTOR_INIT
        </span>
      </div>

      {error || !project ? (
        <div className="mt-4 rounded border border-border bg-bg-surface-raised p-5 text-center">
          <p className="text-xs text-text-secondary">
            {t("orientation.projectError")}
          </p>
        </div>
      ) : (
        <div className="relative mt-4 rounded border border-border bg-bg-surface-raised p-5">
          <span className="absolute inset-x-0 top-0 h-[2px] bg-accent" />
          <div className="flex items-center gap-2">
            <FolderGit2 className="h-4 w-4 text-accent-ink" />
            <h2 className="text-base font-medium text-text-primary">
              {project.title}
            </h2>
          </div>
          <p className="mt-3 text-xs leading-relaxed text-text-secondary">
            {project.description}
          </p>
          <div className="mt-4 border-t border-border pt-3 font-mono text-[10px] text-text-muted">
            STATUS: ACTIVE // WORKWEEK_CYCLE: INITIALIZED
          </div>
        </div>
      )}
    </section>
  );
}

function HowStep({ items }: { items: HowItWorksItem[] }) {
  const { t } = useLocale();
  return (
    <section>
      <div className="flex items-center justify-between border-b border-border pb-2">
        <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
          {t("orientation.howItWorksEyebrow")}
        </span>
        <span className="font-mono text-[10px] text-text-muted">
          5_STAGE_CADENCE
        </span>
      </div>

      <div className="mt-4 flex flex-col gap-2.5">
        {items.map((s, i) => (
          <div
            key={s.title}
            className="flex items-start gap-3 rounded border border-border bg-bg-surface-raised p-3.5 transition-colors hover:border-border-strong"
          >
            <span
              dir="ltr"
              className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border border-border bg-bg-base font-mono text-[10px] text-accent-ink"
            >
              {String(i + 1).padStart(2, "0")}
            </span>
            <div>
              <h3 className="text-xs font-medium text-text-primary">
                {s.title}
              </h3>
              <p className="mt-1 text-xs leading-relaxed text-text-secondary">
                {s.body}
              </p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function ReadyStep({ firstName }: { firstName: string }) {
  const { t } = useLocale();
  return (
    <section className="flex flex-col justify-center text-start">
      <div className="flex items-center gap-2">
        <CheckCircle2 className="h-5 w-5 text-agent-mentor" />
        <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
          INITIALIZATION_COMPLETE
        </span>
      </div>

      <h2 className="mt-3 text-2xl font-medium tracking-tight text-text-primary sm:text-3xl">
        {t("orientation.readyTitle", { name: firstName })}
      </h2>
      <p className="mt-3 text-sm leading-relaxed text-text-secondary sm:text-base">
        {t("orientation.readyBody")}
      </p>

      <div className="mt-6 rounded border border-border bg-bg-surface-raised/40 p-4 font-mono text-xs text-text-muted"></div>
    </section>
  );
}
