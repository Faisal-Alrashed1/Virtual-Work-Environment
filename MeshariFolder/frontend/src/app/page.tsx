"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import {
  GraduationCap,
  Building2,
  ArrowUpRight,
  ChevronDown,
} from "lucide-react";
import { AGENT_ORDER } from "@/lib/agents";
import { useAgents, useLocale } from "@/lib/i18n/locale";
import { ThemeToggle } from "@/components/theme-toggle";
import { LocaleToggle } from "@/components/locale-toggle";

const fadeUp = {
  initial: { opacity: 0, y: 14 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-60px" },
  transition: { duration: 0.45, ease: "easeOut" as const },
};

interface CycleStep {
  label: string;
  text: string;
}

export default function Home() {
  const { t, tRaw } = useLocale();
  const agents = useAgents();
  const cycleSteps = tRaw<CycleStep[]>("landing.cycleSteps");

  return (
    <main className="min-h-screen bg-bg-base text-text-primary selection:bg-accent selection:text-accent-text">
      {/* Top utility bar */}
      <header className="fixed inset-x-0 top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-bg-base/80 px-6 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs font-semibold tracking-wider text-text-primary">
            {t("common.venv")}
          </span>
          <span className="hidden font-mono text-[10px] text-text-muted sm:inline-block"></span>
        </div>
        <div className="flex items-center gap-2">
          <LocaleToggle className="bg-bg-surface" />
          <ThemeToggle className="bg-bg-surface" />
        </div>
      </header>

      {/* ---- HERO SECTION ---- */}
      <section className="relative flex min-h-screen flex-col justify-center border-b border-border bg-blueprint-grid px-6 pt-20">
        <div className="mx-auto w-full max-w-5xl py-20">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className="relative border border-border bg-bg-surface/90 p-8 sm:p-14"
          >
            {/* Technical corner markers */}
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

            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border pb-6">
              <span className="inline-flex items-center gap-2 rounded border border-border bg-bg-base px-2.5 py-1 font-mono text-[11px] text-text-secondary">
                <span className="h-1.5 w-1.5 rounded-full bg-accent" />
                {t("landing.badge")}
              </span>
              <span className="font-mono text-[10px] uppercase tracking-widest text-text-muted">
                SPEC-2026 // PROD_READY
              </span>
            </div>

            <div className="mt-8 max-w-3xl">
              <h1 className="text-4xl font-normal tracking-tight text-text-primary sm:text-6xl sm:leading-[1.1]">
                {t("landing.heroLine1")}
                <br />
                <span className="text-accent-ink">
                  {t("landing.heroLine2")}
                </span>
              </h1>

              <p className="mt-6 max-w-2xl text-base leading-relaxed text-text-secondary sm:text-lg">
                {t("landing.heroSubtitle")}
              </p>
            </div>

            <div className="mt-10 flex flex-wrap items-center gap-4 border-t border-border pt-8">
              <Link
                href="/login"
                className="inline-flex h-10 items-center justify-center rounded border border-accent bg-accent px-6 font-mono text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong"
              >
                {t("landing.getStarted")}
              </Link>
              <Link
                href="/board"
                className="inline-flex h-10 items-center justify-center gap-1.5 rounded border border-border bg-bg-surface px-5 font-mono text-xs text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
              >
                <span>{t("landing.seeTheBoard")}</span>
                <ArrowUpRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          </motion.div>

          <div className="mt-8 flex items-center justify-between font-mono text-[11px] text-text-muted">
            <span className="flex items-center gap-1.5">
              <ChevronDown className="h-3.5 w-3.5 animate-bounce" />
              {t("landing.scrollToExplore")}
            </span>
            <span>COORD: [24.7136° N, 46.6753° E]</span>
          </div>
        </div>
      </section>

      {/* ---- HOW IT WORKS: THE THREE CORE AGENTS ---- */}
      <section className="relative border-b border-border px-6 py-24">
        <div className="mx-auto w-full max-w-5xl">
          <motion.div {...fadeUp} className="border-s-2 border-accent ps-4">
            <p className="font-mono text-[11px] uppercase tracking-wider text-text-muted">
              {t("landing.howItWorksEyebrow")}
            </p>
            <h2 className="mt-1 text-2xl font-medium text-text-primary sm:text-3xl">
              {t("landing.howItWorksTitle")}
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-text-secondary">
              {t("landing.howItWorksBody")}
            </p>
          </motion.div>

          <div className="mt-12 grid gap-5 sm:grid-cols-3">
            {AGENT_ORDER.map((id, i) => {
              const m = agents[id];
              return (
                <motion.div
                  key={id}
                  {...fadeUp}
                  transition={{ ...fadeUp.transition, delay: 0.08 * i }}
                  className="group relative flex flex-col justify-between rounded border border-border bg-bg-surface p-6 transition-colors hover:border-border-strong"
                >
                  {/* Subtle hairline top indicator */}
                  <span
                    className="absolute inset-x-0 top-0 h-[2px]"
                    style={{ backgroundColor: `var(${m.colorVar})` }}
                  />
                  <div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span
                          className="h-2 w-2 rounded-full"
                          style={{ backgroundColor: `var(${m.colorVar})` }}
                        />
                        <h3 className="text-base font-medium text-text-primary">
                          {m.name}
                        </h3>
                      </div>
                      <span className="font-mono text-[10px] text-text-muted">
                        0{i + 1}
                      </span>
                    </div>

                    <p className="mt-1.5 font-mono text-[11px] text-text-muted">
                      {m.role}
                    </p>

                    <p className="mt-4 text-xs leading-relaxed text-text-secondary">
                      {m.description}
                    </p>
                  </div>

                  <div className="mt-6 border-t border-border pt-3 font-mono text-[10px] text-text-muted">
                    STATUS: ACTIVE_DISPATCH
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ---- TWO TRACKS: GRADUATES AND COMPANIES ---- */}
      <section className="relative border-b border-border bg-blueprint-grid px-6 py-24">
        <div className="mx-auto w-full max-w-5xl">
          <motion.div {...fadeUp} className="border-s-2 border-accent ps-4">
            <p className="font-mono text-[11px] uppercase tracking-wider text-text-muted">
              {t("landing.tracksEyebrow")}
            </p>
            <h2 className="mt-1 text-2xl font-medium text-text-primary sm:text-3xl">
              {t("landing.tracksTitle")}
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-text-secondary">
              {t("landing.tracksBody")}
            </p>
          </motion.div>

          <div className="mt-12 grid gap-6 sm:grid-cols-2">
            {/* Student Track */}
            <motion.div
              {...fadeUp}
              className="relative flex flex-col justify-between rounded border border-border bg-bg-surface p-7"
            >
              <span className="absolute inset-x-0 top-0 h-[2px] bg-accent" />
              <div>
                <div className="flex items-center justify-between">
                  <div className="flex h-9 w-9 items-center justify-center rounded border border-border bg-bg-base text-accent-ink">
                    <GraduationCap className="h-4 w-4" strokeWidth={1.75} />
                  </div>
                  <span className="font-mono text-[10px] uppercase text-text-muted">
                    PORTAL // STUDENT
                  </span>
                </div>

                <h3 className="mt-5 text-lg font-medium text-text-primary">
                  {t("landing.tracksStudentTitle")}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                  {t("landing.tracksStudentBody")}
                </p>
              </div>

              <div className="mt-8 border-t border-border pt-6">
                <Link
                  href="/login"
                  className="inline-flex h-9 items-center justify-center rounded border border-accent bg-accent px-5 font-mono text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong"
                >
                  {t("landing.tracksStudentCta")}
                </Link>
              </div>
            </motion.div>

            {/* Company Track */}
            <motion.div
              {...fadeUp}
              transition={{ ...fadeUp.transition, delay: 0.1 }}
              className="relative flex flex-col justify-between rounded border border-border bg-bg-surface p-7"
            >
              <span className="absolute inset-x-0 top-0 h-[2px] bg-border-strong" />
              <div>
                <div className="flex items-center justify-between">
                  <div className="flex h-9 w-9 items-center justify-center rounded border border-border bg-bg-base text-text-secondary">
                    <Building2 className="h-4 w-4" strokeWidth={1.75} />
                  </div>
                  <span className="font-mono text-[10px] uppercase text-text-muted">
                    PORTAL // ENTERPRISE
                  </span>
                </div>

                <h3 className="mt-5 text-lg font-medium text-text-primary">
                  {t("landing.tracksCompanyTitle")}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                  {t("landing.tracksCompanyBody")}
                </p>
              </div>

              <div className="mt-8 border-t border-border pt-6">
                <Link
                  href="/company/register"
                  className="inline-flex h-9 items-center justify-center rounded border border-border bg-bg-base px-5 font-mono text-xs font-medium text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
                >
                  {t("landing.tracksCompanyCta")}
                </Link>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* ---- THE WEEKLY CYCLE ---- */}
      <section className="relative border-b border-border px-6 py-24">
        <div className="mx-auto w-full max-w-5xl">
          <motion.div {...fadeUp} className="border-s-2 border-accent ps-4">
            <p className="font-mono text-[11px] uppercase tracking-wider text-text-muted">
              {t("landing.loopEyebrow")}
            </p>
            <h2 className="mt-1 text-2xl font-medium text-text-primary sm:text-3xl">
              {t("landing.loopTitle")}
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-text-secondary">
              {t("landing.loopBody")}
            </p>
          </motion.div>

          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {cycleSteps.map((step, i) => (
              <motion.div
                key={step.label}
                {...fadeUp}
                transition={{ ...fadeUp.transition, delay: 0.06 * i }}
                className="relative flex flex-col justify-between rounded border border-border bg-bg-surface p-5"
              >
                <div>
                  <div className="flex items-baseline justify-between border-b border-border pb-3">
                    <span className="font-mono text-lg font-medium text-accent-ink">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <span className="font-mono text-[9px] uppercase tracking-wider text-text-muted">
                      PHASE
                    </span>
                  </div>
                  <p className="mt-3 font-mono text-[11px] uppercase tracking-wide text-text-primary">
                    {step.label}
                  </p>
                  <p className="mt-2 text-xs leading-relaxed text-text-secondary">
                    {step.text}
                  </p>
                </div>
                <div className="mt-4 border-t border-border/50 pt-2 font-mono text-[9px] text-text-muted">
                  STAGE_INDEX_{i}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ---- CLOSING CTA & FOOTER ---- */}
      <section className="relative bg-blueprint-grid px-6 py-24 text-center">
        <motion.div
          {...fadeUp}
          className="mx-auto flex max-w-xl flex-col items-center"
        >
          <div className="rounded border border-border bg-bg-surface p-8 sm:p-12">
            <h2 className="text-3xl font-medium tracking-tight text-text-primary sm:text-4xl">
              {t("landing.closingTitle")}
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-text-secondary">
              {t("landing.closingBody")}
            </p>
            <div className="mt-8 flex justify-center">
              <Link
                href="/login"
                className="inline-flex h-10 items-center justify-center rounded border border-accent bg-accent px-8 font-mono text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong"
              >
                {t("landing.getStarted")}
              </Link>
            </div>
          </div>

          <div className="mt-12 flex flex-col items-center gap-2 font-mono text-[11px] text-text-muted">
            <p>{t("common.venv")}</p>
            <p className="text-[10px]">ALL SYSTEMS OPERATIONAL // 2026</p>
          </div>
        </motion.div>
      </section>
    </main>
  );
}
