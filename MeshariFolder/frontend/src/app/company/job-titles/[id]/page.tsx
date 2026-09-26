"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  Database,
  Upload,
  FolderGit2,
  FileText,
  Mail,
  AlertCircle,
  Cpu,
} from "lucide-react";
import { useRequireAuth, ApiError } from "@/lib/auth-context";
import {
  createCompanyProject,
  createInvitation,
  fetchCompanyInvitations,
  fetchCompanyProjects,
  fetchJobTitle,
  fetchMaterials,
  queryKnowledgeBase,
  uploadMaterial,
  type CompanyProjectSummary,
  type Invitation,
  type JobTitle,
  type KnowledgeMaterial,
  type RAGChunk,
} from "@/lib/company";
import { useLocale } from "@/lib/i18n/locale";
import { ThemeToggle } from "@/components/theme-toggle";
import { LocaleToggle } from "@/components/locale-toggle";
import { AccountMenu } from "@/components/nav/account-menu";

// A job title's knowledge base (docs/STAGE3_COMPANY_RAG.md): upload
// pasted text or a file, see what's been chunked/embedded so far, and
// test the actual RAG retrieval against a question — real cosine
// similarity scores, not a mock.
export default function JobTitleDetailPage() {
  const { user, loading: authLoading } = useRequireAuth();
  const params = useParams<{ id: string }>();
  const jobTitleId = params.id;
  const { t, locale } = useLocale();

  const [jobTitle, setJobTitle] = useState<JobTitle | null>(null);
  const [materials, setMaterials] = useState<KnowledgeMaterial[]>([]);
  const [projects, setProjects] = useState<CompanyProjectSummary[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [pasteText, setPasteText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<RAGChunk[] | null>(null);

  const [projectTitle, setProjectTitle] = useState("");
  const [projectDescription, setProjectDescription] = useState("");
  const [projectMaterials, setProjectMaterials] = useState("");
  const [creatingProject, setCreatingProject] = useState(false);

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteProjectId, setInviteProjectId] = useState("");
  const [inviting, setInviting] = useState(false);

  function load() {
    Promise.all([
      fetchJobTitle(jobTitleId),
      fetchMaterials(jobTitleId),
      fetchCompanyProjects(jobTitleId),
      fetchCompanyInvitations(),
    ])
      .then(([jt, mats, projs, invs]) => {
        setJobTitle(jt);
        setMaterials(mats);
        setProjects(projs);
        setInvitations(invs.filter((inv) => inv.jobTitleId === jobTitleId));
        setError(null);
      })
      .catch((err) =>
        setError(
          err instanceof ApiError ? err.message : t("common.genericError"),
        ),
      )
      .finally(() => setLoading(false));
  }

  async function handleCreateProject(e: React.FormEvent) {
    e.preventDefault();
    if (!projectTitle.trim() || !projectDescription.trim()) return;
    setCreatingProject(true);
    setError(null);
    try {
      const created = await createCompanyProject(
        jobTitleId,
        projectTitle.trim(),
        projectDescription.trim(),
        projectMaterials.trim() || undefined,
      );
      setProjects((prev) => [created, ...prev]);
      setProjectTitle("");
      setProjectDescription("");
      setProjectMaterials("");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : t("company.projectCreateError"),
      );
    } finally {
      setCreatingProject(false);
    }
  }

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    if (!inviteEmail.trim()) return;
    setInviting(true);
    setError(null);
    try {
      const created = await createInvitation(
        jobTitleId,
        inviteEmail.trim(),
        inviteProjectId || undefined,
      );
      setInvitations((prev) => [created, ...prev]);
      setInviteEmail("");
      setInviteProjectId("");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : t("company.inviteError"),
      );
    } finally {
      setInviting(false);
    }
  }

  useEffect(() => {
    if (user) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, jobTitleId]);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!pasteText.trim() && !file) return;
    setUploading(true);
    setError(null);
    try {
      const material = await uploadMaterial(
        jobTitleId,
        pasteText.trim() || undefined,
        file || undefined,
      );
      setMaterials((prev) => [material, ...prev]);
      setJobTitle((prev) =>
        prev
          ? {
              ...prev,
              materialCount: prev.materialCount + 1,
              chunkCount: prev.chunkCount + material.chunkCount,
            }
          : prev,
      );
      setPasteText("");
      setFile(null);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : t("company.uploadError"),
      );
    } finally {
      setUploading(false);
    }
  }

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setError(null);
    try {
      const res = await queryKnowledgeBase(jobTitleId, query.trim());
      setResults(res.chunks);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("company.queryError"));
    } finally {
      setSearching(false);
    }
  }

  const BackArrow = locale === "ar" ? ArrowRight : ArrowLeft;

  if (authLoading || !user || loading) {
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
    <main className="grid h-dvh grid-rows-[auto_1fr] bg-bg-base text-text-primary selection:bg-accent selection:text-accent-text">
      {/* Top Architecture Navigation Bar */}
      <header className="z-20 flex h-14 items-center justify-between border-b border-border bg-bg-surface/90 px-6 backdrop-blur-md">
        <div className="flex items-center gap-4">
          <Link
            href="/company"
            className="group flex items-center gap-2 font-mono text-xs text-text-muted transition-colors hover:text-text-primary"
          >
            <BackArrow className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5 rtl:group-hover:translate-x-0.5" />
            <span>{t("common.venv")}</span>
            <span className="text-border-strong">/</span>
            <span>{t("company.nav")}</span>
            <span className="text-border-strong">/</span>
            <span className="text-[10px] text-text-muted">
              {jobTitle?.title}
            </span>
          </Link>

          <div className="hidden items-center gap-2 border-s border-border ps-4 sm:flex">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            <h1 className="font-mono text-xs font-medium uppercase tracking-wider text-text-primary">
              {jobTitle?.title}
            </h1>
          </div>
        </div>

        {/* Global Toolbar Cluster */}
        <div className="flex items-center gap-3">
          <AccountMenu email={user.email} />
          <LocaleToggle className="bg-bg-base" />
          <ThemeToggle className="bg-bg-base" />
        </div>
      </header>

      {/* Main Viewport Content */}
      <div className="thin-scrollbar overflow-y-auto">
        <div className="mx-auto flex max-w-4xl flex-col gap-8 px-6 py-10">
          {error && (
            <div className="flex items-center gap-2 rounded border border-danger/30 bg-danger/10 p-3 font-mono text-xs text-danger">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* JOB TITLE TELEMETRY HEADER */}
          <div className="relative rounded border border-border bg-bg-surface p-6 sm:p-7">
            <span className="absolute inset-x-0 top-0 h-[2px] bg-accent" />
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 text-accent-ink" />
                <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                  JOB_POSITION // CONTEXT_ENGINE
                </span>
              </div>
              <div className="flex items-center gap-2 font-mono text-[10px] text-text-muted">
                <span>CHUNKS: {jobTitle?.chunkCount ?? 0}</span>
                <span>•</span>
                <span>DOCS: {jobTitle?.materialCount ?? 0}</span>
              </div>
            </div>

            <div className="mt-4">
              <h2 className="text-2xl font-medium tracking-tight text-text-primary">
                {jobTitle?.title}
              </h2>
              {jobTitle?.description && (
                <p className="mt-2 text-xs leading-relaxed text-text-secondary">
                  {jobTitle.description}
                </p>
              )}
            </div>
          </div>

          {/* SECTION 1: KNOWLEDGE BASE INGESTION (UPLOAD) */}
          <form
            onSubmit={handleUpload}
            className="relative rounded border border-border bg-bg-surface p-6 sm:p-7"
          >
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

            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <Upload className="h-4 w-4 text-accent-ink" />
                <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                  KNOWLEDGE_INGESTION // EMBEDDINGS
                </span>
              </div>
              <span className="font-mono text-[10px] text-text-muted">
                OPENAI_TEXT_EMBED_3
              </span>
            </div>

            <div className="mt-4">
              <h2 className="text-base font-medium text-text-primary">
                {t("company.uploadTitle")}
              </h2>
              <p className="mt-1 text-xs leading-relaxed text-text-secondary">
                {t("company.uploadBody")}
              </p>
            </div>

            <div className="mt-5 flex flex-col gap-3.5 border-t border-border/60 pt-4">
              <div className="flex flex-col gap-1.5">
                <label className="font-mono text-[11px] text-text-muted">
                  PASTE_TEXT_RAW:
                </label>
                <textarea
                  value={pasteText}
                  onChange={(e) => setPasteText(e.target.value)}
                  rows={4}
                  placeholder={t("company.pasteTextPlaceholder")}
                  className="thin-scrollbar resize-none rounded border border-border bg-bg-surface-raised p-3 text-xs text-text-primary placeholder:text-text-muted transition-colors focus:border-accent focus:outline-none"
                />
              </div>

              <div className="flex items-center justify-center gap-3">
                <span className="h-px flex-1 bg-border/60" />
                <span className="font-mono text-[10px] uppercase text-text-muted">
                  {t("common.or")}
                </span>
                <span className="h-px flex-1 bg-border/60" />
              </div>

              <label className="flex cursor-pointer items-center justify-between rounded border border-dashed border-border bg-bg-surface-raised/40 px-4 py-3 text-xs text-text-secondary transition-colors hover:border-border-strong hover:bg-bg-surface-raised">
                <span className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-accent-ink" />
                  <span className="font-mono text-xs">
                    {file ? file.name : t("onboarding.chooseFile")}
                  </span>
                </span>
                <span className="font-mono text-[10px] text-text-muted">
                  .PDF, .DOCX, .TXT, .MD
                </span>
                <input
                  type="file"
                  accept=".pdf,.docx,.doc,.txt,.md"
                  className="hidden"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </label>

              <div className="pt-2">
                <button
                  type="submit"
                  disabled={uploading || (!pasteText.trim() && !file)}
                  className="inline-flex h-9 items-center justify-center rounded border border-accent bg-accent px-5 font-mono text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {uploading ? t("company.uploading") : t("company.upload")}
                </button>
              </div>
            </div>
          </form>

          {/* SECTION 2: INGESTED MATERIALS ARCHIVE */}
          <div className="relative rounded border border-border bg-bg-surface p-6 sm:p-7">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                {t("company.materialsTitle", {
                  count: String(materials.length),
                })}
              </span>
              <span className="font-mono text-[10px] text-text-muted">
                INGESTED_DOCUMENTS
              </span>
            </div>

            {materials.length === 0 ? (
              <div className="mt-4 rounded border border-dashed border-border bg-bg-base/40 p-6 text-center font-mono text-xs text-text-muted">
                {t("company.noMaterials")}
              </div>
            ) : (
              <div className="mt-4 flex flex-col gap-2.5">
                {materials.map((m) => (
                  <div
                    key={m.id}
                    className="flex flex-col gap-1.5 rounded border border-border bg-bg-surface-raised p-3.5 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <p className="font-mono text-xs font-medium text-text-primary">
                        {m.filename ?? t("company.pastedText")}
                      </p>
                      <span className="rounded border border-border bg-bg-base px-2 py-0.5 font-mono text-[10px] text-text-muted">
                        {t("company.chunksCount", {
                          count: String(m.chunkCount),
                        })}
                      </span>
                    </div>
                    <p className="line-clamp-2 text-xs leading-relaxed text-text-secondary">
                      {m.preview}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* SECTION 3: COMPANY TEMPLATE PROJECTS */}
          <form
            onSubmit={handleCreateProject}
            className="relative rounded border border-border bg-bg-surface p-6 sm:p-7"
          >
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <FolderGit2 className="h-4 w-4 text-accent-ink" />
                <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                  PROJECT_TEMPLATES // ENTERPRISE_SPECS
                </span>
              </div>
              <span className="font-mono text-[10px] text-text-muted">
                AUTONOMOUS_CYCLE
              </span>
            </div>

            <div className="mt-4">
              <h2 className="text-base font-medium text-text-primary">
                {t("company.projectsTitle")}
              </h2>
              <p className="mt-1 text-xs leading-relaxed text-text-secondary">
                {t("company.projectsBody")}
              </p>
            </div>

            <div className="mt-5 flex flex-col gap-3.5 border-t border-border/60 pt-4">
              <div className="flex flex-col gap-1.5">
                <label className="font-mono text-[11px] text-text-muted">
                  PROJECT_TITLE:
                </label>
                <input
                  value={projectTitle}
                  onChange={(e) => setProjectTitle(e.target.value)}
                  placeholder={t("company.projectTitlePlaceholder")}
                  className="h-9 rounded border border-border bg-bg-surface-raised px-3 text-xs text-text-primary placeholder:text-text-muted transition-colors focus:border-accent focus:outline-none"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="font-mono text-[11px] text-text-muted">
                  PROJECT_DESCRIPTION:
                </label>
                <textarea
                  value={projectDescription}
                  onChange={(e) => setProjectDescription(e.target.value)}
                  rows={2}
                  placeholder={t("company.projectDescriptionPlaceholder")}
                  className="thin-scrollbar resize-none rounded border border-border bg-bg-surface-raised p-3 text-xs text-text-primary placeholder:text-text-muted transition-colors focus:border-accent focus:outline-none"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="font-mono text-[11px] text-text-muted">
                  INGESTED_SOURCE_MATERIALS:
                </label>
                <textarea
                  value={projectMaterials}
                  onChange={(e) => setProjectMaterials(e.target.value)}
                  rows={3}
                  placeholder={t("company.projectMaterialsPlaceholder")}
                  className="thin-scrollbar resize-none rounded border border-border bg-bg-surface-raised p-3 text-xs text-text-primary placeholder:text-text-muted transition-colors focus:border-accent focus:outline-none"
                />
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  disabled={
                    creatingProject ||
                    !projectTitle.trim() ||
                    !projectDescription.trim()
                  }
                  className="inline-flex h-9 items-center justify-center rounded border border-accent bg-accent px-5 font-mono text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {creatingProject
                    ? t("common.working")
                    : t("company.addProject")}
                </button>
              </div>

              {projects.length > 0 && (
                <div className="mt-4 flex flex-col gap-2 border-t border-border/60 pt-4">
                  <span className="font-mono text-[10px] uppercase text-text-muted">
                    RECORDED_PROJECT_TEMPLATES:
                  </span>
                  {projects.map((p) => (
                    <div
                      key={p.id}
                      className="rounded border border-border bg-bg-surface-raised p-3.5 transition-colors"
                    >
                      <p className="font-mono text-xs font-medium text-text-primary">
                        {p.title}
                      </p>
                      <p className="mt-1 text-xs text-text-secondary leading-relaxed">
                        {p.description}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </form>

          {/* SECTION 4: INVITATIONS TO CANDIDATES */}
          <form
            onSubmit={handleInvite}
            className="relative rounded border border-border bg-bg-surface p-6 sm:p-7"
          >
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <Mail className="h-4 w-4 text-accent-ink" />
                <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                  DISPATCH // CANDIDATE_INVITATION
                </span>
              </div>
              <span className="font-mono text-[10px] text-text-muted">
                CONSENT_REQUIRED
              </span>
            </div>

            <div className="mt-4">
              <h2 className="text-base font-medium text-text-primary">
                {t("company.inviteTitle")}
              </h2>
              <p className="mt-1 text-xs leading-relaxed text-text-secondary">
                {t("company.inviteBody")}
              </p>
            </div>

            <div className="mt-5 flex flex-col gap-3.5 border-t border-border/60 pt-4">
              <div className="flex flex-col gap-1.5">
                <label className="font-mono text-[11px] text-text-muted">
                  CANDIDATE_EMAIL:
                </label>
                <input
                  type="email"
                  dir="ltr"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder={t("company.inviteEmailPlaceholder")}
                  className="h-9 rounded border border-border bg-bg-surface-raised px-3 text-xs text-text-primary placeholder:text-text-muted transition-colors focus:border-accent focus:outline-none"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="font-mono text-[11px] text-text-muted">
                  ASSIGNED_TRACK_PROJECT:
                </label>
                <div className="relative">
                  <select
                    value={inviteProjectId}
                    onChange={(e) => setInviteProjectId(e.target.value)}
                    className="h-9 w-full appearance-none rounded border border-border bg-bg-surface-raised px-3 pe-8 font-mono text-xs text-text-primary transition-colors focus:border-accent focus:outline-none"
                  >
                    <option value="">{t("company.invitePlatformTrack")}</option>
                    {projects.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.title}
                      </option>
                    ))}
                  </select>
                  <div className="pointer-events-none absolute end-2.5 top-1/2 -translate-y-1/2 font-mono text-xs text-text-muted">
                    ▾
                  </div>
                </div>
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  disabled={inviting || !inviteEmail.trim()}
                  className="inline-flex h-9 items-center justify-center rounded border border-accent bg-accent px-5 font-mono text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {inviting ? t("common.working") : t("company.sendInvite")}
                </button>
              </div>

              {invitations.length > 0 && (
                <div className="mt-4 flex flex-col gap-2 border-t border-border/60 pt-4">
                  <span className="font-mono text-[10px] uppercase text-text-muted">
                    DISPATCHED_INVITATIONS:
                  </span>
                  {invitations.map((inv) => (
                    <div
                      key={inv.id}
                      className="flex flex-wrap items-center justify-between gap-3 rounded border border-border bg-bg-surface-raised p-3.5 transition-colors"
                    >
                      <div>
                        <p
                          dir="ltr"
                          className="text-start font-mono text-xs text-text-primary"
                        >
                          {inv.invitedEmail}
                        </p>
                        {inv.companyProjectTitle && (
                          <p className="mt-0.5 text-xs text-text-secondary">
                            {inv.companyProjectTitle}
                          </p>
                        )}
                        <p className="mt-0.5 font-mono text-[10px] text-text-muted">
                          {inv.emailSent
                            ? t("company.emailSent")
                            : t("company.emailNotSent")}
                        </p>
                      </div>
                      <span className="rounded border border-border bg-bg-base px-2 py-0.5 font-mono text-[10px] uppercase text-text-muted">
                        {t(`company.invitationStatus.${inv.status}`)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </form>

          {/* SECTION 5: RAG RETRIEVAL SANDBOX */}
          <form
            onSubmit={handleSearch}
            className="relative rounded border border-border bg-bg-surface p-6 sm:p-7"
          >
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <Cpu className="h-4 w-4 text-accent-ink" />
                <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                  RAG_QUERY_SANDBOX // COSINE_SIMILARITY
                </span>
              </div>
              <span className="font-mono text-[10px] text-text-muted">
                IN_MEMORY_KNN
              </span>
            </div>

            <div className="mt-4">
              <h2 className="text-base font-medium text-text-primary">
                {t("company.searchTitle")}
              </h2>
              <p className="mt-1 text-xs leading-relaxed text-text-secondary">
                {t("company.searchBody")}
              </p>
            </div>

            <div className="mt-5 flex gap-2 border-t border-border/60 pt-4">
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t("company.searchPlaceholder")}
                className="h-9 flex-1 rounded border border-border bg-bg-surface-raised px-3 text-xs text-text-primary placeholder:text-text-muted transition-colors focus:border-accent focus:outline-none"
              />
              <button
                type="submit"
                disabled={searching || !query.trim()}
                className="inline-flex h-9 shrink-0 items-center justify-center rounded border border-accent bg-accent px-5 font-mono text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-40"
              >
                {searching ? t("common.working") : t("company.search")}
              </button>
            </div>

            {results && (
              <div className="mt-5 flex flex-col gap-2.5 border-t border-border/60 pt-4">
                <span className="font-mono text-[10px] uppercase text-text-muted">
                  RETRIEVED_CHUNKS:
                </span>
                {results.length === 0 ? (
                  <p className="font-mono text-xs text-text-muted">
                    {t("company.noResults")}
                  </p>
                ) : (
                  results.map((chunk) => (
                    <div
                      key={chunk.id}
                      className="rounded border border-border bg-bg-surface-raised p-3.5 transition-colors border-s-2 border-s-accent"
                    >
                      <div className="flex items-center justify-between font-mono text-[10px] text-text-muted">
                        <span>CHUNK_ID_{chunk.id.slice(0, 8)}</span>
                        <span className="text-accent-ink font-semibold">
                          {t("company.score")}: {chunk.score.toFixed(3)}
                        </span>
                      </div>
                      <p className="mt-2 text-xs leading-relaxed text-text-primary">
                        {chunk.content}
                      </p>
                    </div>
                  ))
                )}
              </div>
            )}
          </form>

          {/* Footer Back Link */}
          <div className="border-t border-border pt-4">
            <Link
              href="/company"
              className="group inline-flex items-center gap-1.5 font-mono text-xs text-text-muted transition-colors hover:text-text-primary"
            >
              <BackArrow className="h-3 w-3 transition-transform group-hover:-translate-x-0.5 rtl:group-hover:translate-x-0.5" />
              <span>{t("company.nav")}</span>
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
