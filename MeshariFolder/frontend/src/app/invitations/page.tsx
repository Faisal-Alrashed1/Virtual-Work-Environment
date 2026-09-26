"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  Clock,
  ArrowUpRight,
  AlertCircle,
  Briefcase,
} from "lucide-react";
import { useRequireAuth, ApiError } from "@/lib/auth-context";
import {
  acceptInvitation,
  declineInvitation,
  fetchMyInvitations,
  type InvitationDetail,
} from "@/lib/invitations";
import { useLocale } from "@/lib/i18n/locale";
import { ThemeToggle } from "@/components/theme-toggle";
import { LocaleToggle } from "@/components/locale-toggle";

// A student's own invitations (docs/STAGE3_COMPANY_RAG.md) — the consent
// screen. Accepting isn't a single click: the person has to read exactly
// what the company will (and won't) see and explicitly check a box
// before the Accept button does anything, enforced server-side too
// (POST /invitations/{id}/accept 400s without consent:true).
export default function InvitationsPage() {
  const { user, loading: authLoading, refreshUser } = useRequireAuth();
  const router = useRouter();
  const { t, locale } = useLocale();

  const [invitations, setInvitations] = useState<InvitationDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [consented, setConsented] = useState<Record<string, boolean>>({});
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    fetchMyInvitations()
      .then(setInvitations)
      .catch((err) =>
        setError(
          err instanceof ApiError ? err.message : t("common.genericError"),
        ),
      )
      .finally(() => setLoading(false));
  }, [user, t]);

  async function handleAccept(inv: InvitationDetail) {
    if (!consented[inv.id]) {
      setError(t("invitations.mustConsent"));
      return;
    }
    setBusyId(inv.id);
    setError(null);
    try {
      const updated = await acceptInvitation(inv.id, true);
      setInvitations((prev) =>
        prev.map((i) => (i.id === inv.id ? updated : i)),
      );
      await refreshUser();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : t("invitations.acceptError"),
      );
    } finally {
      setBusyId(null);
    }
  }

  async function handleDecline(inv: InvitationDetail) {
    setBusyId(inv.id);
    setError(null);
    try {
      const updated = await declineInvitation(inv.id);
      setInvitations((prev) =>
        prev.map((i) => (i.id === inv.id ? updated : i)),
      );
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : t("invitations.declineError"),
      );
    } finally {
      setBusyId(null);
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
            href="/board"
            className="group flex items-center gap-2 font-mono text-xs text-text-muted transition-colors hover:text-text-primary"
          >
            <BackArrow className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5 rtl:group-hover:translate-x-0.5" />
            <span>{t("nav.venvBoard")}</span>
            <span className="text-border-strong">/</span>
            <span className="text-[10px] text-text-muted transition-colors group-hover:text-text-secondary">
              INVITATIONS_QUEUE
            </span>
          </Link>

          <div className="hidden items-center gap-2 border-s border-border ps-4 sm:flex">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            <h1 className="font-mono text-xs font-medium uppercase tracking-wider text-text-primary">
              {t("invitations.title")}
            </h1>
          </div>
        </div>

        {/* Global Toolbar Cluster */}
        <div className="flex items-center gap-3">
          <Link
            href="/board"
            className="inline-flex h-8 items-center gap-1.5 rounded border border-border bg-bg-base px-3 font-mono text-xs text-text-secondary transition-colors hover:border-border-strong hover:bg-bg-surface hover:text-text-primary"
          >
            <Briefcase className="h-3.5 w-3.5" />
            <span>{t("nav.homeBoardTitle")}</span>
          </Link>

          <div className="mx-1 h-4 border-s border-border" />

          <LocaleToggle className="bg-bg-base" />
          <ThemeToggle className="bg-bg-base" />
        </div>
      </header>

      {/* Main Stream Area */}
      <div className="thin-scrollbar overflow-y-auto">
        <div className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-10">
          {/* Header Metadata Capsule */}
          <div>
            <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
              ACCESS_CLEARANCE // CANDIDATE_OFFERS
            </span>
            <h2 className="mt-1 text-2xl font-medium tracking-tight text-text-primary">
              {t("invitations.title")}
            </h2>
            <p className="mt-1 text-xs leading-relaxed text-text-secondary">
              {t("invitations.subtitle")}
            </p>
          </div>

          {error && (
            <div className="flex items-center gap-2 rounded border border-danger/30 bg-danger/10 p-3 font-mono text-xs text-danger">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Invitations List */}
          {invitations.length === 0 ? (
            <div className="rounded border border-dashed border-border bg-bg-surface/50 p-10 text-center font-mono text-xs text-text-muted">
              {t("invitations.empty")}
            </div>
          ) : (
            invitations.map((inv) => {
              const isPending = inv.status === "pending";
              const isAccepted = inv.status === "accepted";
              const isDeclined = inv.status === "declined";

              return (
                <div
                  key={inv.id}
                  className="relative rounded border border-border bg-bg-surface p-6 transition-colors"
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

                  {/* Top hairline indicator */}
                  {isPending && (
                    <span className="absolute inset-x-0 top-0 h-[2px] bg-accent" />
                  )}
                  {isAccepted && (
                    <span className="absolute inset-x-0 top-0 h-[2px] bg-agent-mentor" />
                  )}

                  {/* Header Row */}
                  <div className="flex items-start justify-between gap-4 border-b border-border pb-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <Building2 className="h-4 w-4 text-accent-ink" />
                        <h3 className="text-base font-medium text-text-primary">
                          {inv.organizationName}
                        </h3>
                      </div>
                      <p className="mt-1 font-mono text-xs text-text-secondary">
                        {inv.jobTitle}
                      </p>
                      <p className="mt-0.5 font-mono text-[10px] text-text-muted">
                        TRACK:{" "}
                        {inv.companyProjectTitle ??
                          t("invitations.platformTrack")}
                      </p>
                    </div>

                    <span
                      className={`inline-flex items-center gap-1.5 rounded border px-2.5 py-0.5 font-mono text-[10px] uppercase ${
                        isPending
                          ? "border-accent/40 bg-accent/10 text-accent-ink"
                          : isAccepted
                            ? "border-agent-mentor/40 bg-agent-mentor/10 text-agent-mentor"
                            : "border-border bg-bg-base text-text-muted"
                      }`}
                    >
                      {isPending && <Clock className="h-2.5 w-2.5" />}
                      {isAccepted && <CheckCircle2 className="h-2.5 w-2.5" />}
                      {isDeclined && <XCircle className="h-2.5 w-2.5" />}
                      <span>{t(`company.invitationStatus.${inv.status}`)}</span>
                    </span>
                  </div>

                  {/* Pending State & Explicit Consent Protocol */}
                  {isPending && (
                    <div className="mt-4 flex flex-col gap-4">
                      <div className="rounded border border-border bg-bg-surface-raised/40 p-3.5">
                        <div className="flex items-center gap-1.5 border-b border-border/60 pb-2">
                          <ShieldCheck className="h-3.5 w-3.5 text-accent-ink" />
                          <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
                            DATA_ACCESS_DISCLOSURE
                          </span>
                        </div>
                        <p className="mt-2 text-xs leading-relaxed text-text-secondary">
                          {inv.dataSharedNotice}
                        </p>
                      </div>

                      <label className="flex cursor-pointer items-start gap-2.5">
                        <input
                          type="checkbox"
                          checked={Boolean(consented[inv.id])}
                          onChange={(e) =>
                            setConsented((prev) => ({
                              ...prev,
                              [inv.id]: e.target.checked,
                            }))
                          }
                          className="mt-0.5 accent-accent"
                        />
                        <span className="text-xs text-text-primary leading-tight">
                          {t("invitations.consentLabel")}
                        </span>
                      </label>

                      <div className="flex items-center gap-2 border-t border-border pt-4">
                        <button
                          type="button"
                          onClick={() => handleAccept(inv)}
                          disabled={busyId === inv.id || !consented[inv.id]}
                          className="inline-flex h-9 items-center justify-center rounded border border-accent bg-accent px-5 font-mono text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          {busyId === inv.id
                            ? t("common.working")
                            : t("invitations.accept")}
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDecline(inv)}
                          disabled={busyId === inv.id}
                          className="inline-flex h-9 items-center justify-center rounded border border-border bg-bg-base px-4 font-mono text-xs text-text-secondary transition-colors hover:border-border-strong hover:bg-bg-surface-raised hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          {t("invitations.decline")}
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Accepted State Actions */}
                  {isAccepted && (
                    <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
                      <p className="font-mono text-xs text-agent-mentor">
                        ✓ {t("invitations.accepted")}
                      </p>
                      <div className="flex items-center gap-2">
                        <Link
                          href={`/invitations/${inv.id}/visibility`}
                          className="inline-flex h-8 items-center gap-1.5 rounded border border-border bg-bg-surface-raised px-3 font-mono text-xs text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
                        >
                          <span>{t("invitations.seeWhatTheySee")}</span>
                          <ArrowUpRight className="h-3 w-3" />
                        </Link>
                        <button
                          type="button"
                          onClick={() => router.push("/workspace")}
                          className="inline-flex h-8 items-center rounded border border-accent bg-accent px-3 font-mono text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong"
                        >
                          {t("nav.workspace")}
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Declined State */}
                  {isDeclined && (
                    <div className="mt-4 border-t border-border pt-3">
                      <p className="font-mono text-xs text-text-muted">
                        ✕ {t("invitations.declined")}
                      </p>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </main>
  );
}
