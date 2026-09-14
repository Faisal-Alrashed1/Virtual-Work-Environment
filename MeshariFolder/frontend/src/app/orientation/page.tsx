"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useRequireAuth } from "@/lib/auth-context";
import { AGENT_ORDER, AGENTS } from "@/lib/agents";
import { fetchMyExtraAgents, type ExtraAgent } from "@/lib/team";
import { fetchMyProject, type Project } from "@/lib/projects";
import { assignNextTask } from "@/lib/tasks";

const HOW_IT_WORKS = [
  {
    title: "One task at a time",
    body: "The Manager plans each week as one big goal, broken into five subtasks. You get them one at a time, not all at once.",
  },
  {
    title: "Submit with a GitHub link",
    body: "Push your work to a public repo and submit the link. The Mentor reads it and either approves it or sends it back with feedback to revise.",
  },
  {
    title: "The week wraps up together",
    body: "At the end of the week, the Manager and HR review your progress together — then the next week starts right away.",
  },
  {
    title: "Talk to any agent directly",
    body: "The meeting room is open any time for a direct conversation, outside of task threads.",
  },
];

export default function OrientationPage() {
  const { user, loading: authLoading } = useRequireAuth();
  const router = useRouter();

  const [project, setProject] = useState<Project | null>(null);
  const [extraAgents, setExtraAgents] = useState<ExtraAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!user) return;
    (async () => {
      const [existing, agents] = await Promise.all([fetchMyProject(), fetchMyExtraAgents()]);
      setExtraAgents(agents);
      if (existing) {
        setProject(existing);
        setLoading(false);
        return;
      }
      // First time through: nobody's asked the Manager for a project yet
      // (the own-project path is a separate, not-yet-built screen — see
      // docs/STAGE2_OWN_PROJECT.md) — so orientation itself is what
      // triggers it, same call the task board's "ask manager" button
      // makes. weekly_cycle.py's bootstrap is idempotent, so this is
      // safe to call even if it somehow runs twice.
      try {
        await assignNextTask();
        setProject(await fetchMyProject());
      } catch {
        setError(true);
      }
      setLoading(false);
    })();
  }, [user]);

  const firstName = user?.fullName?.split(" ")[0] ?? "there";

  if (authLoading || !user) {
    return (
      <main className="flex flex-1 items-center justify-center">
        <p className="text-sm text-text-muted">Loading...</p>
      </main>
    );
  }

  return (
    <main className="bg-blueprint-grid flex flex-1 justify-center px-6 py-12">
      <div className="w-full max-w-2xl">
        <Link href="/" className="font-mono text-xs text-text-muted hover:text-text-secondary">
          venv
        </Link>
        <h1 className="mt-3 text-2xl font-medium text-text-primary">Welcome, {firstName}</h1>
        <p className="mt-2 text-sm leading-relaxed text-text-secondary">
          Here&apos;s your project, your team, and how the day-to-day works.
        </p>

        {loading ? (
          <div className="mt-8 rounded border border-border bg-bg-surface p-8 text-center">
            <p className="text-sm text-text-muted">Setting things up...</p>
          </div>
        ) : (
          <div className="mt-8 flex flex-col gap-8">
            <section>
              <p className="font-mono text-[11px] text-text-muted">your_project</p>
              {error || !project ? (
                <div className="mt-2 rounded border border-border bg-bg-surface p-4">
                  <p className="text-sm text-text-secondary">
                    Couldn&apos;t reach the Manager just now — no project yet. Head to the task
                    board and ask for one when you&apos;re ready.
                  </p>
                </div>
              ) : (
                <div className="mt-2 rounded border border-border-strong bg-bg-surface-raised p-4">
                  <h2 className="text-base font-medium text-text-primary">{project.title}</h2>
                  <p className="mt-1.5 text-sm leading-relaxed text-text-secondary">
                    {project.description}
                  </p>
                </div>
              )}
            </section>

            <section>
              <p className="font-mono text-[11px] text-text-muted">your_team</p>
              <div className="mt-2 grid gap-3 sm:grid-cols-3">
                {AGENT_ORDER.map((id) => {
                  const meta = AGENTS[id];
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
                  <div
                    key={agent.id}
                    className="rounded border border-dashed border-border p-3"
                  >
                    <div className="flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full bg-text-muted" />
                      <span className="font-medium text-text-primary">{agent.name}</span>
                    </div>
                    <p className="mt-1.5 text-xs text-text-secondary">{agent.description}</p>
                  </div>
                ))}
              </div>
            </section>

            <section>
              <p className="font-mono text-[11px] text-text-muted">how_it_works</p>
              <div className="mt-2 flex flex-col gap-2">
                {HOW_IT_WORKS.map((step, i) => (
                  <div key={i} className="rounded border border-border bg-bg-surface p-3">
                    <div className="flex items-baseline gap-2">
                      <span className="font-mono text-[11px] text-text-muted">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <span className="text-sm font-medium text-text-primary">{step.title}</span>
                    </div>
                    <p className="mt-1 text-sm leading-relaxed text-text-secondary">
                      {step.body}
                    </p>
                  </div>
                ))}
              </div>
            </section>

            <button
              type="button"
              onClick={() => router.push("/board")}
              className="self-start rounded border border-accent bg-accent px-4 py-2 text-sm font-medium text-accent-text transition-colors hover:bg-accent-strong"
            >
              Go to board
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
