"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Upload } from "lucide-react";
import { ApiError, useRequireAuth } from "@/lib/auth-context";
import { api, type AgentCatalogApiOut, type ApiTrack } from "@/lib/api";
import { SELECTABLE_ONLY_TRACKS } from "@/lib/tracks";
import { createOwnProject } from "@/lib/projects";
import { useLocale, useTrackLabels } from "@/lib/i18n/locale";
import { ThemeToggle } from "@/components/theme-toggle";
import { LocaleToggle } from "@/components/locale-toggle";

type Step = "loading" | "cv" | "qa" | "track" | "agents" | "project" | "already-done";

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
  const { t } = useLocale();
  const trackLabels = useTrackLabels();

  const [step, setStep] = useState<Step>("loading");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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
  const [selectedAgentIds, setSelectedAgentIds] = useState<Set<string>>(new Set());

  // project — Stage 2's optional own-project path (docs/STAGE2_OWN_PROJECT.md)
  const [projectChoice, setProjectChoice] = useState<"manager" | "own" | null>(null);
  const [ownTitle, setOwnTitle] = useState("");
  const [ownDescription, setOwnDescription] = useState("");

  // On load, check whether onboarding's already done so we don't make a
  // graduate redo it. Mid-flow resume (picking back up exactly on the qa/
  // track/agents step from a previous session) isn't supported yet — see
  // docs/STAGE2_ONBOARDING_FLOW.md — so anything short of "complete" just
  // starts the wizard fresh from the CV step.
  useEffect(() => {
    if (!user) return;
    api.onboarding
      .state()
      .then((s) => setStep(s.onboarding_stage === "complete" ? "already-done" : "cv"))
      .catch(() => setStep("cv"));
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
      setError(err instanceof ApiError ? err.message : t("onboarding.errors.couldntReadFile"));
    } finally {
      setBusy(false);
    }
  }

  async function handleSkipCv() {
    // Every other path through this wizard ends at orientation
    // (handleFinishProject, below) — skipping the CV step is still a
    // path through onboarding, so it shouldn't be the one way to skip
    // the walkthrough entirely.
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
      const result = await api.onboarding.submitQa(cleanAnswers, introText.trim());
      setSuggestedTrack(result.suggested_track);
      setSelectedTrack(result.suggested_track);
      setReasoning(result.reasoning);
      setStep("track");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("onboarding.errors.couldntSaveAnswers"));
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
      setError(err instanceof ApiError ? err.message : t("onboarding.errors.couldntSaveTrack"));
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
      setError(err instanceof ApiError ? err.message : t("onboarding.errors.couldntSaveTeam"));
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
        await createOwnProject(ownTitle.trim(), ownDescription.trim());
      }
      // "manager" (or no explicit choice) needs nothing here — orientation
      // itself triggers the Manager's assign-task call when it finds no
      // project yet.
      router.push("/orientation");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("onboarding.errors.couldntSetUpProject"));
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
      // Reset local wizard state too, then drop back to the first step.
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
      setStep("cv");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("onboarding.errors.couldntRestart"));
    } finally {
      setBusy(false);
    }
  }

  if (authLoading || !user || step === "loading") {
    return (
      <main className="flex flex-1 items-center justify-center">
        <p className="text-sm text-text-muted">{t("common.loading")}</p>
      </main>
    );
  }

  return (
    <main className="bg-blueprint-grid flex flex-1 flex-col items-center justify-center px-6 py-12">
      <div className="w-full max-w-lg">
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <Link href="/" className="font-mono text-xs text-text-muted hover:text-text-secondary">
              {t("common.venv")}
            </Link>
            <div className="flex items-center gap-2">
              <LocaleToggle />
              <ThemeToggle />
            </div>
          </div>
          {step !== "already-done" && (
            <p className="mt-3 text-center text-xs text-text-muted">
              {t("onboarding.stepOf", { n: STEP_NUMBER[step], total: TOTAL_STEPS })}
            </p>
          )}
        </div>

        {step === "already-done" && (
          <Panel>
            <h1 className="text-2xl font-medium text-text-primary">{t("onboarding.alreadyDoneTitle")}</h1>
            <p className="mt-2 text-sm leading-relaxed text-text-secondary">
              {t("onboarding.alreadyDoneBody")}
            </p>
            {error && <p className="mt-3 text-sm text-danger">{error}</p>}
            <div className="mt-5 flex items-center gap-3">
              <PrimaryButton onClick={() => router.push("/board")}>
                {t("onboarding.goToBoard")}
              </PrimaryButton>
              <button
                type="button"
                onClick={handleRestart}
                disabled={busy}
                className="text-sm text-text-muted transition-colors hover:text-text-secondary disabled:opacity-50"
              >
                {busy ? t("onboarding.resetting") : t("onboarding.goThroughAgain")}
              </button>
            </div>
          </Panel>
        )}

        {step === "cv" && (
          <Panel>
            <h1 className="text-2xl font-medium text-text-primary">{t("onboarding.cvTitle")}</h1>
            <p className="mt-2 text-sm leading-relaxed text-text-secondary">
              {t("onboarding.cvBody")}
            </p>

            <label className="mt-5 flex cursor-pointer flex-col items-center gap-2 rounded border border-dashed border-border bg-bg-surface-raised px-4 py-8 text-center transition-colors hover:border-border-strong">
              <Upload size={18} className="text-text-muted" />
              <span className="text-sm text-text-secondary">
                {file ? file.name : t("onboarding.chooseFile")}
              </span>
              <input
                type="file"
                accept=".pdf,.docx,.txt"
                className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </label>

            {error && <p className="mt-3 text-sm text-danger">{error}</p>}

            <div className="mt-5 flex items-center justify-between">
              <SkipLink onClick={handleSkipCv}>{t("onboarding.skipForNow")}</SkipLink>
              <PrimaryButton onClick={handleUpload} disabled={!file || busy}>
                {busy ? t("onboarding.reading") : t("onboarding.continue")}
              </PrimaryButton>
            </div>
          </Panel>
        )}

        {step === "qa" && (
          <Panel>
            <h1 className="text-2xl font-medium text-text-primary">{t("onboarding.qaTitle")}</h1>
            <p className="mt-2 text-sm leading-relaxed text-text-secondary">
              {t("onboarding.qaBody")}
            </p>

            <div className="mt-5 space-y-4">
              {questions.map((q, i) => (
                <div key={i}>
                  <label className="text-sm text-text-secondary">{q}</label>
                  <input
                    type="text"
                    value={answers[i] ?? ""}
                    onChange={(e) => setAnswers((prev) => ({ ...prev, [i]: e.target.value }))}
                    className="mt-1.5 w-full rounded border border-border bg-bg-surface-raised px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-border-strong focus:outline-none"
                  />
                </div>
              ))}

              <div>
                <label className="text-sm text-text-secondary">
                  {t("onboarding.anythingElseLabel")}
                </label>
                <textarea
                  value={introText}
                  onChange={(e) => setIntroText(e.target.value)}
                  rows={3}
                  placeholder={t("onboarding.optionalPlaceholder")}
                  className="mt-1.5 w-full resize-none rounded border border-border bg-bg-surface-raised px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-border-strong focus:outline-none"
                />
              </div>
            </div>

            {error && <p className="mt-3 text-sm text-danger">{error}</p>}

            <div className="mt-5 flex justify-end">
              <PrimaryButton onClick={handleSubmitQa} disabled={busy}>
                {busy ? t("onboarding.saving") : t("onboarding.continue")}
              </PrimaryButton>
            </div>
          </Panel>
        )}

        {step === "track" && suggestedTrack && selectedTrack && (
          <Panel>
            <h1 className="text-2xl font-medium text-text-primary">{t("onboarding.trackTitle")}</h1>
            <p className="mt-2 text-sm leading-relaxed text-text-secondary">{reasoning}</p>

            <div className="mt-5 rounded border border-border-strong bg-bg-surface-raised p-3">
              <p className="text-xs text-text-muted">{t("onboarding.suggestedLabel")}</p>
              <p className="mt-0.5 text-sm text-text-primary">{trackLabels[suggestedTrack]}</p>
            </div>

            <div className="mt-4">
              <label className="text-sm text-text-secondary">{t("onboarding.notQuiteRight")}</label>
              <select
                value={selectedTrack}
                onChange={(e) => setSelectedTrack(e.target.value as ApiTrack)}
                className="mt-1.5 w-full rounded border border-border bg-bg-surface-raised px-3 py-2 text-sm text-text-primary focus:border-border-strong focus:outline-none"
              >
                {SELECTABLE_ONLY_TRACKS.map((tr) => (
                  <option key={tr} value={tr}>
                    {trackLabels[tr]}
                  </option>
                ))}
              </select>
            </div>

            {error && <p className="mt-3 text-sm text-danger">{error}</p>}

            <div className="mt-5 flex justify-end">
              <PrimaryButton onClick={handleApproveTrack} disabled={busy}>
                {busy ? t("onboarding.saving") : t("onboarding.continue")}
              </PrimaryButton>
            </div>
          </Panel>
        )}

        {step === "agents" && (
          <Panel>
            <h1 className="text-2xl font-medium text-text-primary">{t("onboarding.teamTitle")}</h1>
            <p className="mt-2 text-sm leading-relaxed text-text-secondary">
              {t("onboarding.teamBody")}
            </p>

            <div className="mt-5 space-y-2">
              {catalog.map((agent) => (
                <label
                  key={agent.id}
                  className="flex cursor-pointer items-start gap-3 rounded border border-border bg-bg-surface-raised p-3 transition-colors hover:border-border-strong"
                >
                  <input
                    type="checkbox"
                    checked={selectedAgentIds.has(agent.id)}
                    onChange={() => toggleAgent(agent.id)}
                    className="mt-0.5 accent-accent"
                  />
                  <span>
                    <span className="block text-sm text-text-primary">{agent.name}</span>
                    <span className="block text-xs text-text-secondary">{agent.description}</span>
                  </span>
                </label>
              ))}
            </div>

            {error && <p className="mt-3 text-sm text-danger">{error}</p>}

            <div className="mt-5 flex justify-end">
              <PrimaryButton onClick={handleApproveAgents} disabled={busy}>
                {busy ? t("onboarding.saving") : t("onboarding.finish")}
              </PrimaryButton>
            </div>
          </Panel>
        )}
        {step === "project" && (
          <Panel>
            <h1 className="text-2xl font-medium text-text-primary">{t("onboarding.projectTitle")}</h1>
            <p className="mt-2 text-sm leading-relaxed text-text-secondary">
              {t("onboarding.projectBody")}
            </p>

            <div className="mt-5 space-y-2">
              <button
                type="button"
                onClick={() => setProjectChoice("manager")}
                className={`w-full rounded border p-3 text-start transition-colors ${
                  projectChoice === "manager"
                    ? "border-accent bg-bg-surface-raised"
                    : "border-border hover:border-border-strong"
                }`}
              >
                <span className="block text-sm font-medium text-text-primary">
                  {t("onboarding.letManagerPlan")}
                </span>
                <span className="block text-xs text-text-secondary">
                  {t("onboarding.letManagerPlanDesc")}
                </span>
              </button>

              <button
                type="button"
                onClick={() => setProjectChoice("own")}
                className={`w-full rounded border p-3 text-start transition-colors ${
                  projectChoice === "own"
                    ? "border-accent bg-bg-surface-raised"
                    : "border-border hover:border-border-strong"
                }`}
              >
                <span className="block text-sm font-medium text-text-primary">
                  {t("onboarding.ownProject")}
                </span>
                <span className="block text-xs text-text-secondary">
                  {t("onboarding.ownProjectDesc")}
                </span>
              </button>
            </div>

            {projectChoice === "own" && (
              <div className="mt-4 flex flex-col gap-3">
                <div>
                  <label className="text-sm text-text-secondary">
                    {t("onboarding.projectTitleLabel")}
                  </label>
                  <input
                    value={ownTitle}
                    onChange={(e) => setOwnTitle(e.target.value)}
                    placeholder={t("onboarding.projectTitlePlaceholder")}
                    className="mt-1.5 w-full rounded border border-border bg-bg-surface-raised px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-border-strong focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-sm text-text-secondary">{t("onboarding.whatIsItLabel")}</label>
                  <textarea
                    value={ownDescription}
                    onChange={(e) => setOwnDescription(e.target.value)}
                    rows={3}
                    placeholder={t("onboarding.whatIsItPlaceholder")}
                    className="mt-1.5 w-full resize-none rounded border border-border bg-bg-surface-raised px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-border-strong focus:outline-none"
                  />
                </div>
              </div>
            )}

            {error && <p className="mt-3 text-sm text-danger">{error}</p>}

            <div className="mt-5 flex justify-end">
              <PrimaryButton onClick={handleFinishProject} disabled={!projectChoice || busy}>
                {busy ? t("onboarding.settingUp") : t("onboarding.finish")}
              </PrimaryButton>
            </div>
          </Panel>
        )}
      </div>
    </main>
  );
}

function Panel({ children }: { children: React.ReactNode }) {
  return <div className="rounded border border-border bg-bg-surface p-5">{children}</div>;
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
      className="rounded border border-accent bg-accent px-4 py-2 text-sm font-medium text-accent-text transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50"
    >
      {children}
    </button>
  );
}

function SkipLink({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="text-xs text-text-muted transition-colors hover:text-text-secondary"
    >
      {children}
    </button>
  );
}
