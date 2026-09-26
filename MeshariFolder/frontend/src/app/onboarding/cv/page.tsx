"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Upload,
  Sparkles,
  RotateCcw,
  ArrowRight,
  ArrowLeft,
  AlertCircle,
} from "lucide-react";
import { ApiError, useRequireAuth } from "@/lib/auth-context";
import { api, type AgentCatalogApiOut, type ApiTrack } from "@/lib/api";
import { SELECTABLE_ONLY_TRACKS } from "@/lib/tracks";
import { createOwnProject } from "@/lib/projects";
import { useLocale, useTrackLabels } from "@/lib/i18n/locale";
import { ThemeToggle } from "@/components/theme-toggle";
import { LocaleToggle } from "@/components/locale-toggle";

type Step =
  | "loading"
  | "cv"
  | "qa"
  | "track"
  | "agents"
  | "project"
  | "already-done";

const STEP_NUMBER: Record<Step, number> = {
  loading: 0,
  cv: 1,
  qa: 2,
  track: 3,
  agents: 4,
  project: 5,
  "already-done": 0,
};

const TOTAL_STEPS = 5;

export default function OnboardingPage() {
  const { user, loading: authLoading, refreshUser } = useRequireAuth();
  const router = useRouter();
  const { t, locale } = useLocale();
  const trackLabels = useTrackLabels();

  const [step, setStep] = useState<Step>("loading");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [resumedAt, setResumedAt] = useState<Step | null>(null);

  // cv
  const [file, setFile] = useState<File | null>(null);

  // qa
  const [questions, setQuestions] = useState<string[]>([]);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [introText, setIntroText] = useState("");

  // track
  const [suggestedTrack, setSuggestedTrack] = useState<ApiTrack | null>(null);
  const [reasoning, setReasoning] = useState("");
  const [selectedTrack, setSelectedTrack] = useState<ApiTrack | null>(null);

  // agents
  const [catalog, setCatalog] = useState<AgentCatalogApiOut[]>([]);
  const [selectedAgentIds, setSelectedAgentIds] = useState<Set<string>>(
    new Set(),
  );

  // project
  const [projectChoice, setProjectChoice] = useState<"manager" | "own" | null>(
    null,
  );
  const [ownTitle, setOwnTitle] = useState("");
  const [ownDescription, setOwnDescription] = useState("");
  const [ownMaterialsText, setOwnMaterialsText] = useState("");
  const [ownMaterialsFiles, setOwnMaterialsFiles] = useState<File[]>([]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await api.onboarding.resume();
        if (cancelled) return;
        if (r.onboarding_stage === "complete") {
          setStep("already-done");
          return;
        }
        if (!r.resumable) {
          setStep("cv");
          return;
        }
        const agentCatalog = await api.onboarding.catalog();
        if (cancelled) return;
        setCatalog(agentCatalog);
        if (r.onboarding_stage === "qa") {
          setQuestions(r.questions);
          setIntroText(r.intro_text ?? "");
          setStep("qa");
          setResumedAt("qa");
        } else if (r.onboarding_stage === "track" && r.suggested_track) {
          setSuggestedTrack(r.suggested_track);
          setSelectedTrack(r.suggested_track);
          setReasoning(r.reasoning ?? "");
          setStep("track");
          setResumedAt("track");
        } else if (r.onboarding_stage === "agents") {
          setSelectedAgentIds(new Set(r.suggested_agents.map((a) => a.id)));
          setStep("agents");
          setResumedAt("agents");
        } else {
          setStep("cv");
        }
      } catch {
        if (!cancelled) setStep("cv");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user]);

  async function handleUpload() {
    if (!file) return;
    setError(null);
    setBusy(true);
    try {
      const [result, agentCatalog] = await Promise.all([
        api.onboarding.uploadCv(file),
        api.onboarding.catalog(),
      ]);
      setQuestions(result.questions);
      setCatalog(agentCatalog);
      setStep("qa");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : t("onboarding.errors.couldntReadFile"),
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleSkipCv() {
    router.push("/orientation");
  }

  async function handleSubmitQa() {
    setError(null);
    setBusy(true);
    try {
      const cleanAnswers: Record<string, string> = {};
      for (const [i, text] of Object.entries(answers)) {
        if (text.trim()) cleanAnswers[i] = text.trim();
      }
      const result = await api.onboarding.submitQa(
        cleanAnswers,
        introText.trim(),
      );
      setSuggestedTrack(result.suggested_track);
      setSelectedTrack(result.suggested_track);
      setReasoning(result.reasoning);
      setStep("track");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : t("onboarding.errors.couldntSaveAnswers"),
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleApproveTrack() {
    setError(null);
    setBusy(true);
    try {
      const override = selectedTrack !== suggestedTrack ? selectedTrack : null;
      const result = await api.onboarding.approveTrack(override);
      setSelectedAgentIds(new Set(result.suggested_agents.map((a) => a.id)));
      setStep("agents");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : t("onboarding.errors.couldntSaveTrack"),
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleApproveAgents() {
    setError(null);
    setBusy(true);
    try {
      await api.onboarding.approveAgents(Array.from(selectedAgentIds));
      await refreshUser();
      setStep("project");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : t("onboarding.errors.couldntSaveTeam"),
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleFinishProject() {
    setError(null);
    setBusy(true);
    try {
      if (projectChoice === "own") {
        if (!ownTitle.trim() || !ownDescription.trim()) {
          setError(t("onboarding.titleDescRequired"));
          setBusy(false);
          return;
        }
        await createOwnProject(
          ownTitle.trim(),
          ownDescription.trim(),
          ownMaterialsText.trim() || undefined,
          ownMaterialsFiles.length > 0 ? ownMaterialsFiles : undefined,
        );
      }
      router.push("/orientation");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : t("onboarding.errors.couldntSetUpProject"),
      );
      setBusy(false);
    }
  }

  function toggleAgent(id: string) {
    setSelectedAgentIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleRestart() {
    setError(null);
    setBusy(true);
    try {
      await api.onboarding.reset();
      setFile(null);
      setQuestions([]);
      setAnswers({});
      setIntroText("");
      setSuggestedTrack(null);
      setSelectedTrack(null);
      setSelectedAgentIds(new Set());
      setProjectChoice(null);
      setOwnTitle("");
      setOwnDescription("");
      setOwnMaterialsText("");
      setOwnMaterialsFiles([]);
      setStep("cv");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : t("onboarding.errors.couldntRestart"),
      );
    } finally {
      setBusy(false);
    }
  }

  const BackArrow = locale === "ar" ? ArrowRight : ArrowLeft;

  if (authLoading || !user || step === "loading") {
    return (
      <main className="flex min-h-screen flex-1 items-center justify-center bg-bg-base text-text-primary">
        <div className="flex items-center gap-2 rounded border border-border bg-bg-surface px-4 py-3 font-mono text-xs text-text-muted">
          <span className="h-2 w-2 animate-ping rounded-full bg-accent" />
          <span>{t("common.loading")}</span>
        </div>
      </main>
    );
  }

  return (
    <main className="relative flex min-h-screen flex-1 flex-col items-center justify-center bg-blueprint-grid px-6 py-16 text-text-primary selection:bg-accent selection:text-accent-text">
      {/* Top Engineering Header Bar */}
      <header className="fixed inset-x-0 top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-bg-base/80 px-6 backdrop-blur-md">
        <Link
          href="/"
          className="group flex items-center gap-2 font-mono text-xs text-text-muted transition-colors hover:text-text-primary"
        >
          <BackArrow className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5 rtl:group-hover:translate-x-0.5" />
          <span>{t("common.venv")}</span>
          <span className="text-border-strong">/</span>
          <span className="text-[10px] text-text-muted sm:inline">
            INTAKE_PROTOCOL
          </span>
        </Link>
        <div className="flex items-center gap-2">
          <LocaleToggle className="bg-bg-surface" />
          <ThemeToggle className="bg-bg-surface" />
        </div>
      </header>

      {/* Main Console Container */}
      <div className="w-full max-w-xl">
        {/* Step Progress Telemetry Header */}
        {step !== "already-done" && (
          <div className="mb-6 flex flex-col gap-2">
            <div className="flex items-center justify-between font-mono text-[10px] text-text-muted">
              <span>
                PROGRESS: STAGE_0{STEP_NUMBER[step]} 0{TOTAL_STEPS}
              </span>
              <span>CALIBRATION_FLOW</span>
            </div>
            {/* 5-Step Segmented Bar */}
            <div className="grid grid-cols-5 gap-1.5">
              {[1, 2, 3, 4, 5].map((idx) => {
                const isCurrent = idx === STEP_NUMBER[step];
                const isPast = idx < STEP_NUMBER[step];
                return (
                  <div
                    key={idx}
                    className={`h-1 rounded-full transition-colors ${
                      isPast
                        ? "bg-accent"
                        : isCurrent
                          ? "bg-accent/80 animate-pulse"
                          : "bg-border"
                    }`}
                  />
                );
              })}
            </div>

            {resumedAt !== null && resumedAt === step && (
              <div className="mt-1 flex items-center gap-1.5 rounded border border-border bg-bg-surface px-2.5 py-1 font-mono text-[10px] text-text-secondary">
                <Sparkles className="h-3 w-3 text-accent-ink" />
                <span>{t("onboarding.resumedNote")}</span>
              </div>
            )}
          </div>
        )}

        {/* STEP: ALREADY DONE */}
        {step === "already-done" && (
          <Panel>
            <div className="border-b border-border pb-3">
              <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                PROFILE // COMPLETED
              </span>
              <h1 className="mt-1 text-xl font-medium text-text-primary">
                {t("onboarding.alreadyDoneTitle")}
              </h1>
            </div>

            <p className="mt-4 text-xs leading-relaxed text-text-secondary">
              {t("onboarding.alreadyDoneBody")}
            </p>

            {error && (
              <div className="mt-4 flex items-center gap-2 rounded border border-danger/30 bg-danger/10 p-2.5 text-xs text-danger">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
              <button
                type="button"
                onClick={handleRestart}
                disabled={busy}
                className="inline-flex items-center gap-1.5 font-mono text-xs text-text-muted transition-colors hover:text-text-primary disabled:opacity-50"
              >
                <RotateCcw className="h-3 w-3" />
                <span>
                  {busy
                    ? t("onboarding.resetting")
                    : t("onboarding.goThroughAgain")}
                </span>
              </button>

              <PrimaryButton onClick={() => router.push("/board")}>
                {t("onboarding.goToBoard")}
              </PrimaryButton>
            </div>
          </Panel>
        )}

        {/* STEP: CV UPLOAD */}
        {step === "cv" && (
          <Panel>
            <div className="border-b border-border pb-3">
              <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                PHASE_01 // RESUME_PARSING
              </span>
              <h1 className="mt-1 text-xl font-medium text-text-primary">
                {t("onboarding.cvTitle")}
              </h1>
            </div>

            <p className="mt-3 text-xs leading-relaxed text-text-secondary">
              {t("onboarding.cvBody")}
            </p>

            <label className="mt-5 flex cursor-pointer flex-col items-center justify-center gap-2 rounded border border-dashed border-border bg-bg-surface-raised/40 p-8 text-center transition-colors hover:border-border-strong hover:bg-bg-surface-raised">
              <div className="flex h-10 w-10 items-center justify-center rounded-full border border-border bg-bg-base text-accent-ink">
                <Upload className="h-4 w-4" />
              </div>
              <span className="font-mono text-xs font-medium text-text-primary">
                {file ? file.name : t("onboarding.chooseFile")}
              </span>
              <span className="font-mono text-[10px] text-text-muted">
                FORMATS: .PDF, .DOCX, .TXT // MAX 10MB
              </span>
              <input
                type="file"
                accept=".pdf,.docx,.txt"
                className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </label>

            {error && (
              <div className="mt-4 flex items-center gap-2 rounded border border-danger/30 bg-danger/10 p-2.5 text-xs text-danger">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="mt-6 flex items-center justify-between border-t border-border pt-4">
              <SkipLink onClick={handleSkipCv}>
                {t("onboarding.skipForNow")}
              </SkipLink>
              <PrimaryButton onClick={handleUpload} disabled={!file || busy}>
                {busy ? t("onboarding.reading") : t("onboarding.continue")}
              </PrimaryButton>
            </div>
          </Panel>
        )}

        {/* STEP: Q&A */}
        {step === "qa" && (
          <Panel>
            <div className="border-b border-border pb-3">
              <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                PHASE_02 // ADAPTIVE_DIAGNOSTICS
              </span>
              <h1 className="mt-1 text-xl font-medium text-text-primary">
                {t("onboarding.qaTitle")}
              </h1>
            </div>

            <p className="mt-3 text-xs leading-relaxed text-text-secondary">
              {t("onboarding.qaBody")}
            </p>

            <div className="mt-5 flex flex-col gap-4">
              {questions.map((q, i) => (
                <div key={i} className="flex flex-col gap-1.5">
                  <label className="font-mono text-xs text-text-primary">
                    <span className="me-1 text-accent-ink">0{i + 1}.</span> {q}
                  </label>
                  <input
                    type="text"
                    value={answers[i] ?? ""}
                    onChange={(e) =>
                      setAnswers((prev) => ({ ...prev, [i]: e.target.value }))
                    }
                    className="h-9 rounded border border-border bg-bg-surface-raised px-3 text-xs text-text-primary placeholder:text-text-muted transition-colors focus:border-accent focus:outline-none"
                  />
                </div>
              ))}

              <div className="flex flex-col gap-1.5">
                <label className="font-mono text-xs text-text-secondary">
                  {t("onboarding.anythingElseLabel")}
                </label>
                <textarea
                  value={introText}
                  onChange={(e) => setIntroText(e.target.value)}
                  rows={3}
                  placeholder={t("onboarding.optionalPlaceholder")}
                  className="thin-scrollbar resize-none rounded border border-border bg-bg-surface-raised p-3 text-xs text-text-primary placeholder:text-text-muted transition-colors focus:border-accent focus:outline-none"
                />
              </div>
            </div>

            {error && (
              <div className="mt-4 flex items-center gap-2 rounded border border-danger/30 bg-danger/10 p-2.5 text-xs text-danger">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="mt-6 flex justify-end border-t border-border pt-4">
              <PrimaryButton onClick={handleSubmitQa} disabled={busy}>
                {busy ? t("onboarding.saving") : t("onboarding.continue")}
              </PrimaryButton>
            </div>
          </Panel>
        )}

        {/* STEP: TRACK SUGGESTION */}
        {step === "track" && suggestedTrack && selectedTrack && (
          <Panel>
            <div className="border-b border-border pb-3">
              <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                PHASE_03 // SPECIALIZATION_ALIGNMENT
              </span>
              <h1 className="mt-1 text-xl font-medium text-text-primary">
                {t("onboarding.trackTitle")}
              </h1>
            </div>

            <p className="mt-3 text-xs leading-relaxed text-text-secondary">
              {reasoning}
            </p>

            {/* AI Suggested Track Badge */}
            <div className="relative mt-4 rounded border border-accent/40 bg-accent/5 p-4">
              <span className="absolute inset-y-0 start-0 w-[2px] bg-accent" />
              <div className="flex items-center justify-between">
                <span className="font-mono text-[10px] uppercase tracking-wider text-accent-ink">
                  {t("onboarding.suggestedLabel")}
                </span>
                <span className="font-mono text-[10px] text-text-muted">
                  CONFIDENCE: HIGH
                </span>
              </div>
              <p className="mt-1 font-mono text-sm font-semibold text-text-primary">
                {trackLabels[suggestedTrack]}
              </p>
            </div>

            {/* Override Dropdown */}
            <div className="mt-5 flex flex-col gap-1.5">
              <label className="font-mono text-xs text-text-secondary">
                {t("onboarding.notQuiteRight")}
              </label>
              <div className="relative">
                <select
                  value={selectedTrack}
                  onChange={(e) => setSelectedTrack(e.target.value as ApiTrack)}
                  className="h-9 w-full appearance-none rounded border border-border bg-bg-surface-raised px-3 pe-8 font-mono text-xs text-text-primary transition-colors focus:border-accent focus:outline-none"
                >
                  {SELECTABLE_ONLY_TRACKS.map((tr) => (
                    <option
                      key={tr}
                      value={tr}
                      className="bg-bg-surface-raised text-text-primary"
                    >
                      {trackLabels[tr]}
                    </option>
                  ))}
                </select>
                <div className="pointer-events-none absolute end-2.5 top-1/2 -translate-y-1/2 font-mono text-xs text-text-muted">
                  ▾
                </div>
              </div>
            </div>

            {error && (
              <div className="mt-4 flex items-center gap-2 rounded border border-danger/30 bg-danger/10 p-2.5 text-xs text-danger">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="mt-6 flex justify-end border-t border-border pt-4">
              <PrimaryButton onClick={handleApproveTrack} disabled={busy}>
                {busy ? t("onboarding.saving") : t("onboarding.continue")}
              </PrimaryButton>
            </div>
          </Panel>
        )}

        {/* STEP: TEAM ROSTER SELECTION */}
        {step === "agents" && (
          <Panel>
            <div className="border-b border-border pb-3">
              <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                PHASE_04 // TEAM_CONFIGURATION
              </span>
              <h1 className="mt-1 text-xl font-medium text-text-primary">
                {t("onboarding.teamTitle")}
              </h1>
            </div>

            <p className="mt-3 text-xs leading-relaxed text-text-secondary">
              {t("onboarding.teamBody")}
            </p>

            <div className="mt-5 flex flex-col gap-2.5">
              {catalog.map((agent) => {
                const isSelected = selectedAgentIds.has(agent.id);
                return (
                  <label
                    key={agent.id}
                    className={`flex cursor-pointer items-start gap-3 rounded border p-3 transition-colors ${
                      isSelected
                        ? "border-accent bg-bg-surface-raised"
                        : "border-border bg-bg-surface-raised/40 hover:border-border-strong hover:bg-bg-surface-raised"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleAgent(agent.id)}
                      className="mt-0.5 accent-accent"
                    />
                    <div className="flex-1">
                      <span className="font-mono text-xs font-medium text-text-primary">
                        {agent.name}
                      </span>
                      <p className="mt-0.5 text-xs leading-relaxed text-text-secondary">
                        {agent.description}
                      </p>
                    </div>
                  </label>
                );
              })}
            </div>

            {error && (
              <div className="mt-4 flex items-center gap-2 rounded border border-danger/30 bg-danger/10 p-2.5 text-xs text-danger">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="mt-6 flex justify-end border-t border-border pt-4">
              <PrimaryButton onClick={handleApproveAgents} disabled={busy}>
                {busy ? t("onboarding.saving") : t("onboarding.finish")}
              </PrimaryButton>
            </div>
          </Panel>
        )}

        {/* STEP: PROJECT SELECTION */}
        {step === "project" && (
          <Panel>
            <div className="border-b border-border pb-3">
              <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                PHASE_05 // WORKFLOW_SOURCE
              </span>
              <h1 className="mt-1 text-xl font-medium text-text-primary">
                {t("onboarding.projectTitle")}
              </h1>
            </div>

            <p className="mt-3 text-xs leading-relaxed text-text-secondary">
              {t("onboarding.projectBody")}
            </p>

            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              <button
                type="button"
                onClick={() => setProjectChoice("manager")}
                className={`relative flex flex-col justify-between rounded border p-4 text-start transition-colors ${
                  projectChoice === "manager"
                    ? "border-accent bg-bg-surface-raised"
                    : "border-border bg-bg-surface-raised/40 hover:border-border-strong"
                }`}
              >
                {projectChoice === "manager" && (
                  <span className="absolute inset-x-0 top-0 h-[2px] bg-accent" />
                )}
                <div>
                  <span className="font-mono text-xs font-medium text-text-primary">
                    {t("onboarding.letManagerPlan")}
                  </span>
                  <p className="mt-1 text-xs text-text-secondary leading-relaxed">
                    {t("onboarding.letManagerPlanDesc")}
                  </p>
                </div>
              </button>

              <button
                type="button"
                onClick={() => setProjectChoice("own")}
                className={`relative flex flex-col justify-between rounded border p-4 text-start transition-colors ${
                  projectChoice === "own"
                    ? "border-accent bg-bg-surface-raised"
                    : "border-border bg-bg-surface-raised/40 hover:border-border-strong"
                }`}
              >
                {projectChoice === "own" && (
                  <span className="absolute inset-x-0 top-0 h-[2px] bg-accent" />
                )}
                <div>
                  <span className="font-mono text-xs font-medium text-text-primary">
                    {t("onboarding.ownProject")}
                  </span>
                  <p className="mt-1 text-xs text-text-secondary leading-relaxed">
                    {t("onboarding.ownProjectDesc")}
                  </p>
                </div>
              </button>
            </div>

            {/* Custom Project Specifications Form */}
            {projectChoice === "own" && (
              <div className="mt-5 flex flex-col gap-3.5 border-t border-border pt-4">
                <div className="flex flex-col gap-1.5">
                  <label className="font-mono text-xs text-text-secondary">
                    {t("onboarding.projectTitleLabel")}
                  </label>
                  <input
                    value={ownTitle}
                    onChange={(e) => setOwnTitle(e.target.value)}
                    placeholder={t("onboarding.projectTitlePlaceholder")}
                    className="h-9 rounded border border-border bg-bg-surface-raised px-3 text-xs text-text-primary placeholder:text-text-muted transition-colors focus:border-accent focus:outline-none"
                  />
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="font-mono text-xs text-text-secondary">
                    {t("onboarding.whatIsItLabel")}
                  </label>
                  <textarea
                    value={ownDescription}
                    onChange={(e) => setOwnDescription(e.target.value)}
                    rows={3}
                    placeholder={t("onboarding.whatIsItPlaceholder")}
                    className="thin-scrollbar resize-none rounded border border-border bg-bg-surface-raised p-3 text-xs text-text-primary placeholder:text-text-muted transition-colors focus:border-accent focus:outline-none"
                  />
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="font-mono text-xs text-text-secondary">
                    {t("onboarding.materialsLabel")}
                  </label>
                  <p className="text-[10px] text-text-muted font-mono">
                    {t("onboarding.materialsHint")}
                  </p>
                  <textarea
                    value={ownMaterialsText}
                    onChange={(e) => setOwnMaterialsText(e.target.value)}
                    rows={3}
                    placeholder={t("onboarding.materialsPlaceholder")}
                    className="thin-scrollbar resize-none rounded border border-border bg-bg-surface-raised p-3 text-xs text-text-primary placeholder:text-text-muted transition-colors focus:border-accent focus:outline-none"
                  />
                  <label className="mt-1 flex cursor-pointer items-center justify-between rounded border border-dashed border-border bg-bg-surface-raised/40 px-3 py-2 text-xs text-text-secondary transition-colors hover:border-border-strong hover:bg-bg-surface-raised">
                    <span className="flex items-center gap-2">
                      <Upload className="h-3.5 w-3.5 text-text-muted" />
                      <span className="font-mono text-xs">
                        {ownMaterialsFiles.length > 0
                          ? t("onboarding.materialsFilesChosen", {
                              n: ownMaterialsFiles.length,
                            })
                          : t("onboarding.materialsChooseFiles")}
                      </span>
                    </span>
                    <span className="font-mono text-[10px] text-text-muted">
                      MAX 3 FILES
                    </span>
                    <input
                      type="file"
                      accept=".pdf,.docx,.txt"
                      multiple
                      className="hidden"
                      onChange={(e) =>
                        setOwnMaterialsFiles(
                          Array.from(e.target.files ?? []).slice(0, 3),
                        )
                      }
                    />
                  </label>
                </div>
              </div>
            )}

            {error && (
              <div className="mt-4 flex items-center gap-2 rounded border border-danger/30 bg-danger/10 p-2.5 text-xs text-danger">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="mt-6 flex justify-end border-t border-border pt-4">
              <PrimaryButton
                onClick={handleFinishProject}
                disabled={!projectChoice || busy}
              >
                {busy ? t("onboarding.settingUp") : t("onboarding.finish")}
              </PrimaryButton>
            </div>
          </Panel>
        )}

        {/* Footer Meta Strip */}
        <div className="mt-6 flex items-center justify-between px-2 font-mono text-[10px] text-text-muted">
          <span>SPEC // AI_QUALIFICATION_ENGINE</span>
          <span>EST_TIME: ~3 MIN</span>
        </div>
      </div>
    </main>
  );
}

function Panel({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative rounded border border-border bg-bg-surface p-6 sm:p-7">
      {/* Corner crosshair markers */}
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

      {/* Top Hairline Amber Indicator */}
      <span className="absolute inset-x-0 top-0 h-[2px] bg-accent" />
      {children}
    </div>
  );
}

function PrimaryButton({
  onClick,
  disabled,
  children,
}: {
  onClick: () => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="inline-flex h-9 items-center justify-center rounded border border-accent bg-accent px-5 font-mono text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50"
    >
      {children}
    </button>
  );
}

function SkipLink({
  onClick,
  children,
}: {
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="font-mono text-xs text-text-muted transition-colors hover:text-text-primary"
    >
      {children}
    </button>
  );
}
