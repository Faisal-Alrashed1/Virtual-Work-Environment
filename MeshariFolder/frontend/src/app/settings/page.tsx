"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  User,
  ShieldCheck,
  FileText,
  Sliders,
  CheckCircle2,
  AlertCircle,
  Briefcase,
  ArrowUpRight,
} from "lucide-react";
import { useRequireAuth, ApiError } from "@/lib/auth-context";
import { api, type ApiTrack } from "@/lib/api";
import { useLocale, useTrackLabels } from "@/lib/i18n/locale";
import { AccountMenu } from "@/components/nav/account-menu";
import { ThemeToggle } from "@/components/theme-toggle";
import { LocaleToggle } from "@/components/locale-toggle";

// The settings page: the usual things a person expects to control on any
// site (their name, password, language, theme) plus the one thing
// specific to Venv — updating the CV that feeds the Manager's planning.
// Kept as three independent forms (profile / password / preferences) so
// one save never risks the others: renaming yourself shouldn't require
// re-typing a password, and vice versa.
export default function SettingsPage() {
  const { user, loading: authLoading, refreshUser } = useRequireAuth();
  const { t, locale } = useLocale();
  const trackLabels = useTrackLabels();

  const [track, setTrack] = useState<ApiTrack | null>(null);

  const [fullName, setFullName] = useState("");
  const [nameBusy, setNameBusy] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);
  const [nameSaved, setNameSaved] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [pwBusy, setPwBusy] = useState(false);
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwSaved, setPwSaved] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (user) setFullName(user.fullName);
  }, [user]);

  useEffect(() => {
    if (user)
      api
        .me()
        .then((me) => setTrack(me.track as ApiTrack))
        .catch(() => {});
  }, [user]);

  async function saveName() {
    const name = fullName.trim();
    if (!name) return;
    setNameBusy(true);
    setNameError(null);
    setNameSaved(false);
    try {
      await api.updateMe({ full_name: name });
      await refreshUser();
      setNameSaved(true);
    } catch (err) {
      setNameError(
        err instanceof ApiError
          ? err.message
          : t("settings.errors.couldntSaveName"),
      );
    } finally {
      setNameBusy(false);
    }
  }

  async function savePassword() {
    if (!currentPassword || !newPassword) return;
    setPwBusy(true);
    setPwError(null);
    setPwSaved(false);
    try {
      await api.updateMe({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setPwSaved(true);
    } catch (err) {
      setPwError(
        err instanceof ApiError
          ? err.message
          : t("settings.errors.couldntSavePassword"),
      );
    } finally {
      setPwBusy(false);
    }
  }

  const BackArrow = locale === "ar" ? ArrowRight : ArrowLeft;

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
              SYSTEM_PREFERENCES
            </span>
          </Link>

          <div className="hidden items-center gap-2 border-s border-border ps-4 sm:flex">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            <h1 className="font-mono text-xs font-medium uppercase tracking-wider text-text-primary">
              {t("nav.settingsTitle")}
            </h1>
          </div>
        </div>

        {/* Global Toolbar Cluster */}
        <div className="flex items-center gap-3">
          <Link
            href="/workspace"
            className="inline-flex h-8 items-center gap-1.5 rounded border border-border bg-bg-base px-3 font-mono text-xs text-text-secondary transition-colors hover:border-border-strong hover:bg-bg-surface hover:text-text-primary"
          >
            <Briefcase className="h-3.5 w-3.5" />
            <span>{t("nav.workspace")}</span>
          </Link>

          <div className="mx-1 h-4 border-s border-border" />

          <AccountMenu email={user.email} />
          <LocaleToggle className="bg-bg-base" />
          <ThemeToggle className="bg-bg-base" />
        </div>
      </header>

      {/* Main Settings Body */}
      <div className="thin-scrollbar overflow-y-auto">
        <div className="mx-auto flex max-w-2xl flex-col gap-8 px-6 py-10">
          {/* PROFILE MODULE */}
          <Section
            icon={<User className="h-4 w-4 text-accent-ink" />}
            tag="MODULE_01 // IDENTITY"
            title={t("settings.profile.title")}
            body={t("settings.profile.body")}
          >
            <Field label={t("settings.profile.emailLabel")}>
              <div className="rounded border border-border bg-bg-base/70 px-3 py-2 font-mono text-xs text-text-secondary">
                <span dir="ltr">{user.email}</span>
              </div>
            </Field>

            <Field label={t("settings.profile.nameLabel")}>
              <input
                value={fullName}
                onChange={(e) => {
                  setFullName(e.target.value);
                  setNameSaved(false);
                }}
                className="h-9 w-full rounded border border-border bg-bg-surface-raised px-3 text-xs text-text-primary transition-colors focus:border-accent focus:outline-none"
              />
            </Field>

            {track && (
              <Field label={t("settings.profile.trackLabel")}>
                <div className="rounded border border-border bg-bg-base/70 px-3 py-2 font-mono text-xs text-text-secondary">
                  {trackLabels[track]}
                </div>
              </Field>
            )}

            {nameError && (
              <div className="flex items-center gap-2 rounded border border-danger/30 bg-danger/10 p-2.5 text-xs text-danger">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                <span>{nameError}</span>
              </div>
            )}

            {nameSaved && !nameError && (
              <div className="flex items-center gap-2 rounded border border-agent-mentor/30 bg-agent-mentor/10 p-2.5 text-xs text-agent-mentor">
                <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                <span>{t("settings.saved")}</span>
              </div>
            )}

            <div className="pt-2">
              <button
                type="button"
                onClick={saveName}
                disabled={
                  nameBusy ||
                  !fullName.trim() ||
                  fullName.trim() === user.fullName
                }
                className="inline-flex h-9 items-center justify-center rounded border border-accent bg-accent px-5 font-mono text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-40"
              >
                {nameBusy ? t("common.working") : t("settings.profile.save")}
              </button>
            </div>
          </Section>

          {/* PASSWORD MODULE */}
          <Section
            icon={<ShieldCheck className="h-4 w-4 text-accent-ink" />}
            tag="MODULE_02 // AUTH_KEY"
            title={t("settings.password.title")}
            body={t("settings.password.body")}
          >
            <Field label={t("settings.password.currentLabel")}>
              <input
                type="password"
                dir="ltr"
                value={currentPassword}
                onChange={(e) => {
                  setCurrentPassword(e.target.value);
                  setPwSaved(false);
                }}
                placeholder="••••••••"
                className="h-9 w-full rounded border border-border bg-bg-surface-raised px-3 text-xs text-text-primary transition-colors focus:border-accent focus:outline-none"
              />
            </Field>

            <Field label={t("settings.password.newLabel")}>
              <input
                type="password"
                dir="ltr"
                value={newPassword}
                onChange={(e) => {
                  setNewPassword(e.target.value);
                  setPwSaved(false);
                }}
                placeholder="••••••••"
                className="h-9 w-full rounded border border-border bg-bg-surface-raised px-3 text-xs text-text-primary transition-colors focus:border-accent focus:outline-none"
              />
            </Field>

            {pwError && (
              <div className="flex items-center gap-2 rounded border border-danger/30 bg-danger/10 p-2.5 text-xs text-danger">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                <span>{pwError}</span>
              </div>
            )}

            {pwSaved && !pwError && (
              <div className="flex items-center gap-2 rounded border border-agent-mentor/30 bg-agent-mentor/10 p-2.5 text-xs text-agent-mentor">
                <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                <span>{t("settings.saved")}</span>
              </div>
            )}

            <div className="pt-2">
              <button
                type="button"
                onClick={savePassword}
                disabled={pwBusy || !currentPassword || !newPassword}
                className="inline-flex h-9 items-center justify-center rounded border border-accent bg-accent px-5 font-mono text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-40"
              >
                {pwBusy ? t("common.working") : t("settings.password.save")}
              </button>
            </div>
          </Section>

          {/* CV CONTEXT MODULE */}
          <Section
            icon={<FileText className="h-4 w-4 text-accent-ink" />}
            tag="MODULE_03 // CURRICULUM_VITAE"
            title={t("settings.cv.title")}
            body={t("settings.cv.body")}
          >
            <div className="flex items-center justify-between rounded border border-border bg-bg-base/50 p-4">
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded border border-border bg-bg-surface text-accent-ink">
                  <FileText className="h-4 w-4" />
                </div>
                <div>
                  <span className="font-mono text-xs font-medium text-text-primary">
                    {user.hasCv ? "ACTIVE_CV_SYNCHRONIZED" : "NO_CV_RECORDED"}
                  </span>
                  <p className="font-mono text-[10px] text-text-muted">
                    LAST_UPDATE: REGISTERED // AUTOMATIC_INGESTION
                  </p>
                </div>
              </div>

              <Link
                href="/profile/cv"
                className="inline-flex h-8 items-center gap-1.5 rounded border border-border bg-bg-surface px-3 font-mono text-xs text-text-secondary transition-colors hover:border-border-strong hover:bg-bg-surface-raised hover:text-text-primary"
              >
                <span>{t("settings.cv.cta")}</span>
                <ArrowUpRight className="h-3 w-3" />
              </Link>
            </div>
          </Section>

          {/* PREFERENCES MODULE */}
          <Section
            icon={<Sliders className="h-4 w-4 text-accent-ink" />}
            tag="MODULE_04 // LOCALIZATION"
            title={t("settings.preferences.title")}
            body={t("settings.preferences.body")}
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="flex items-center justify-between rounded border border-border bg-bg-base/50 p-3.5">
                <div>
                  <span className="font-mono text-xs font-medium text-text-primary">
                    {t("settings.preferences.language")}
                  </span>
                  <p className="font-mono text-[10px] text-text-muted">
                    INTERFACE // I18N
                  </p>
                </div>
                <LocaleToggle className="bg-bg-surface" />
              </div>

              <div className="flex items-center justify-between rounded border border-border bg-bg-base/50 p-3.5">
                <div>
                  <span className="font-mono text-xs font-medium text-text-primary">
                    {t("settings.preferences.theme")}
                  </span>
                  <p className="font-mono text-[10px] text-text-muted">
                    COLOR_SCHEME // PALETTE
                  </p>
                </div>
                <ThemeToggle className="bg-bg-surface" />
              </div>
            </div>
          </Section>

          {/* Footer Back Link */}
          <div className="border-t border-border pt-4">
            <Link
              href="/board"
              className="group inline-flex items-center gap-1.5 font-mono text-xs text-text-muted transition-colors hover:text-text-primary"
            >
              <BackArrow className="h-3 w-3 transition-transform group-hover:-translate-x-0.5 rtl:group-hover:translate-x-0.5" />
              <span>{t("nav.venvBoard")}</span>
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}

function Section({
  icon,
  tag,
  title,
  body,
  children,
}: {
  icon: React.ReactNode;
  tag: string;
  title: string;
  body: string;
  children: React.ReactNode;
}) {
  return (
    <div className="relative rounded border border-border bg-bg-surface p-6 sm:p-7">
      {/* Corner crosshairs */}
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
          {icon}
          <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
            {tag}
          </span>
        </div>
        <span className="font-mono text-[10px] text-text-muted">
          SYS.CONFIG
        </span>
      </div>

      <div className="mt-4">
        <h2 className="text-base font-medium text-text-primary">{title}</h2>
        <p className="mt-1 text-xs leading-relaxed text-text-secondary">
          {body}
        </p>
      </div>

      <div className="mt-5 flex flex-col gap-3.5 border-t border-border/60 pt-4">
        {children}
      </div>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="font-mono text-[11px] text-text-muted">{label}</label>
      {children}
    </div>
  );
}
