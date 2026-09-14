"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { AGENT_ORDER, AGENTS } from "@/lib/agents";

const fadeUp = {
  initial: { opacity: 0, y: 16 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.5, ease: "easeOut" as const },
};

const CYCLE_STEPS = [
  { label: "assign", text: "The manager hands you one scoped task at a time." },
  { label: "build", text: "You do the work and submit a GitHub link." },
  { label: "review", text: "The mentor reviews it — approve, or revise and resubmit." },
  { label: "grow", text: "At week's end, HR evaluates your progress and consistency." },
];

export default function Home() {
  return (
    <main className="h-dvh snap-y snap-mandatory overflow-y-auto overflow-x-hidden">
      {/* ---- hero ---- */}
      <section className="bg-blueprint-grid flex min-h-dvh snap-start flex-col items-center justify-center px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="flex max-w-2xl flex-col items-center text-center"
        >
          <span className="rounded border border-border bg-bg-surface px-3 py-1 font-mono text-xs text-text-secondary">
            stage 1 · ai-powered web apps
          </span>
          <h1 className="mt-6 text-5xl font-medium tracking-tight text-text-primary sm:text-6xl">
            Your first job,
            <br />
            <span className="text-accent">before your first job.</span>
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-text-secondary">
            Venv is a simulated workplace for recent graduates. A manager
            assigns real tasks, a mentor reviews your code, and HR tracks how
            you grow — three AI agents sharing one file on you.
          </p>
          <div className="mt-8 flex items-center gap-4">
            <Link
              href="/login"
              className="rounded border border-accent bg-accent px-6 py-3 text-sm font-medium text-accent-text transition-colors hover:bg-accent-strong"
            >
              Get started
            </Link>
            <Link
              href="/board"
              className="text-sm text-text-secondary transition-colors hover:text-text-primary"
            >
              See the board →
            </Link>
          </div>
          <p className="mt-16 animate-pulse font-mono text-[11px] text-text-muted">
            scroll to explore ↓
          </p>
        </motion.div>
      </section>

      {/* ---- how it works: the three agents ---- */}
      <section className="flex min-h-dvh snap-start flex-col justify-center px-6 py-16">
        <div className="mx-auto w-full max-w-5xl">
          <motion.div {...fadeUp}>
            <p className="font-mono text-[11px] text-text-muted">how_it_works</p>
            <h2 className="mt-2 text-3xl font-medium text-text-primary">
              Three agents. One shared file.
            </h2>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-text-secondary">
              They don&apos;t keep separate notes. Everything the mentor sees,
              HR sees. Everything HR notes, the manager&apos;s next task
              accounts for. No agent works from a stale picture of you.
            </p>
          </motion.div>

          <div className="mt-10 grid gap-4 sm:grid-cols-3">
            {AGENT_ORDER.map((id, i) => {
              const m = AGENTS[id];
              return (
                <motion.div
                  key={id}
                  {...fadeUp}
                  transition={{ ...fadeUp.transition, delay: 0.1 * i }}
                  className="relative overflow-hidden rounded border border-border bg-bg-surface p-5"
                >
                  <span
                    className="absolute inset-x-0 top-0 h-[3px]"
                    style={{ backgroundColor: `var(${m.colorVar})` }}
                  />
                  <div className="flex items-center gap-2">
                    <span
                      className="h-2.5 w-2.5 rounded-full"
                      style={{ backgroundColor: `var(${m.colorVar})` }}
                    />
                    <h3 className="text-lg font-medium text-text-primary">
                      {m.name}
                    </h3>
                  </div>
                  <p className="mt-1 font-mono text-[11px] text-text-muted">
                    {m.role}
                  </p>
                  <p className="mt-3 text-sm leading-relaxed text-text-secondary">
                    {m.description}
                  </p>
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ---- the weekly cycle ---- */}
      <section className="bg-blueprint-grid flex min-h-dvh snap-start flex-col justify-center px-6 py-16">
        <div className="mx-auto w-full max-w-4xl">
          <motion.div {...fadeUp}>
            <p className="font-mono text-[11px] text-text-muted">the_loop</p>
            <h2 className="mt-2 text-3xl font-medium text-text-primary">
              A week at a time.
            </h2>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-text-secondary">
              Each week is one big task, broken into five. You get them one by
              one — finish, get reviewed, move on. It&apos;s the rhythm of a
              real team, without the real-world stakes.
            </p>
          </motion.div>

          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {CYCLE_STEPS.map((step, i) => (
              <motion.div
                key={step.label}
                {...fadeUp}
                transition={{ ...fadeUp.transition, delay: 0.08 * i }}
                className="rounded border border-border bg-bg-surface p-5"
              >
                <span className="font-mono text-2xl text-accent">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <p className="mt-2 font-mono text-[11px] uppercase tracking-wide text-text-muted">
                  {step.label}
                </p>
                <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                  {step.text}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ---- closing CTA ---- */}
      <section className="flex min-h-dvh snap-start flex-col items-center justify-center px-6 text-center">
        <motion.div {...fadeUp} className="flex max-w-xl flex-col items-center">
          <h2 className="text-4xl font-medium tracking-tight text-text-primary">
            Ready to clock in?
          </h2>
          <p className="mt-4 text-base leading-relaxed text-text-secondary">
            Upload your CV, meet your team, and get your first task. Everything
            you build is yours to keep.
          </p>
          <Link
            href="/login"
            className="mt-8 rounded border border-accent bg-accent px-6 py-3 text-sm font-medium text-accent-text transition-colors hover:bg-accent-strong"
          >
            Get started
          </Link>
          <p className="mt-16 font-mono text-xs text-text-muted">venv</p>
        </motion.div>
      </section>
    </main>
  );
}
