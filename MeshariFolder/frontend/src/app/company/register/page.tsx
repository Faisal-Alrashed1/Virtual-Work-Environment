"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  KeyRound,
  AlertCircle,
} from "lucide-react";
import { ApiError, useAuth } from "@/lib/auth-context";
import { registerCompany } from "@/lib/company";
import { useLocale } from "@/lib/i18n/locale";
import { ThemeToggle } from "@/components/theme-toggle";
import { LocaleToggle } from "@/components/locale-toggle";

type Mode = "found" | "join";
type Role = "admin" | "hr" | "tech_lead";

// Company registration (docs/STAGE3_COMPANY_RAG.md): found a brand new
// company (becomes its first admin) or join an existing one with a
// join code a teammate shared, picking your own role. No email/invite
// system exists in this app, so joining is self-serve — a deliberate
// MVP simplification, not a security boundary.
export default function CompanyRegisterPage() {
  const { login } = useAuth();
  const router = useRouter();
  const { t, locale } = useLocale();

  const [mode, setMode] = useState<Mode>("found");
  const [companyName, setCompanyName] = useState("");
  const [field, setField] = useState("");
  const [joinCode, setJoinCode] = useState("");
  const [role, setRole] = useState<Role>("hr");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const roleLabels: Record<Role, string> = {
    admin: t("companyRegister.roles.admin"),
    hr: t("companyRegister.roles.hr"),
    tech_lead: t("companyRegister.roles.techLead"),
  };

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await registerCompany(
        mode === "found"
          ? {
              email,
              password,
              full_name: fullName,
              company_name: companyName,
              field: field || undefined,
            }
          : {
              email,
              password,
              full_name: fullName,
              join_code: joinCode.trim(),
              role,
            },
      );
      await login(email, password);
      router.push("/company");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : t("common.genericError"),
      );
    } finally {
      setBusy(false);
    }
  }

  const BackArrow = locale === "ar" ? ArrowRight : ArrowLeft;

  return (
    <main className="relative flex min-h-screen flex-1 flex-col items-center justify-center bg-blueprint-grid px-6 py-16 text-text-primary selection:bg-accent selection:text-accent-text">
      {/* Top utility header */}
      <header className="fixed inset-x-0 top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-bg-base/80 px-6 backdrop-blur-md">
        <Link
          href="/login"
          className="group flex items-center gap-2 font-mono text-xs text-text-muted transition-colors hover:text-text-primary"
        >
          <BackArrow className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5 rtl:group-hover:translate-x-0.5" />
          <span>{t("common.venv")}</span>
          <span className="hidden text-border-strong sm:inline">/</span>
          <span className="hidden text-[10px] text-text-muted sm:inline">
            SYS.ORG_INTAKE
          </span>
        </Link>
        <div className="flex items-center gap-2">
          <LocaleToggle className="bg-bg-surface" />
          <ThemeToggle className="bg-bg-surface" />
        </div>
      </header>

      {/* Main card */}
      <div className="w-full max-w-sm">
        <div className="relative rounded border border-border bg-bg-surface p-6 sm:p-7">
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

          {/* Header */}
          <div className="border-b border-border pb-4">
            <div className="flex items-center justify-between font-mono text-[10px] uppercase tracking-wider text-text-muted">
              <span className="flex items-center gap-1.5">
                {mode === "found" ? (
                  <Building2 className="h-3 w-3 text-accent-ink" />
                ) : (
                  <KeyRound className="h-3 w-3 text-accent-ink" />
                )}
                ENTERPRISE_PORTAL
              </span>
              <span>STAGE_03</span>
            </div>
            <h1 className="mt-2 text-xl font-medium text-text-primary">
              {t("companyRegister.title")}
            </h1>
            <p className="mt-1 text-xs leading-relaxed text-text-secondary">
              {t("companyRegister.subtitle")}
            </p>
          </div>

          {/* Segmented Mode Switcher */}
          <div className="mt-5 grid grid-cols-2 gap-1 rounded border border-border bg-bg-base p-1 font-mono text-xs">
            <button
              type="button"
              onClick={() => {
                setMode("found");
                setError(null);
              }}
              className={`rounded px-3 py-1.5 transition-colors ${
                mode === "found"
                  ? "bg-bg-surface text-text-primary font-medium border border-border"
                  : "text-text-muted hover:text-text-secondary"
              }`}
            >
              {t("companyRegister.foundTab")}
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("join");
                setError(null);
              }}
              className={`rounded px-3 py-1.5 transition-colors ${
                mode === "join"
                  ? "bg-bg-surface text-text-primary font-medium border border-border"
                  : "text-text-muted hover:text-text-secondary"
              }`}
            >
              {t("companyRegister.joinTab")}
            </button>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="mt-5 flex flex-col gap-3.5">
            {mode === "found" ? (
              <>
                <Field label={t("companyRegister.companyNameLabel")}>
                  <input
                    required
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    placeholder={t("companyRegister.companyNamePlaceholder")}
                    className="h-9 rounded border border-border bg-bg-surface-raised px-3 text-sm text-text-primary placeholder:text-text-muted transition-colors focus:border-accent focus:outline-none"
                  />
                </Field>
                <Field label={t("companyRegister.fieldLabel")}>
                  <input
                    value={field}
                    onChange={(e) => setField(e.target.value)}
                    placeholder={t("companyRegister.fieldPlaceholder")}
                    className="h-9 rounded border border-border bg-bg-surface-raised px-3 text-sm text-text-primary placeholder:text-text-muted transition-colors focus:border-accent focus:outline-none"
                  />
                </Field>
              </>
            ) : (
              <>
                <Field label={t("companyRegister.joinCodeLabel")}>
                  <input
                    required
                    dir="ltr"
                    value={joinCode}
                    onChange={(e) => setJoinCode(e.target.value)}
                    placeholder={t("companyRegister.joinCodePlaceholder")}
                    className="h-9 rounded border border-border bg-bg-surface-raised px-3 font-mono text-sm uppercase text-text-primary placeholder:font-sans placeholder:normal-case placeholder:text-text-muted transition-colors focus:border-accent focus:outline-none"
                  />
                </Field>
                <Field label={t("companyRegister.roleLabel")}>
                  <div className="relative">
                    <select
                      value={role}
                      onChange={(e) => setRole(e.target.value as Role)}
                      className="h-9 w-full appearance-none rounded border border-border bg-bg-surface-raised px-3 text-sm text-text-primary transition-colors focus:border-accent focus:outline-none pe-8"
                    >
                      {(Object.keys(roleLabels) as Role[]).map((r) => (
                        <option
                          key={r}
                          value={r}
                          className="bg-bg-surface-raised text-text-primary"
                        >
                          {roleLabels[r]}
                        </option>
                      ))}
                    </select>
                    <div className="pointer-events-none absolute end-2.5 top-1/2 -translate-y-1/2 font-mono text-xs text-text-muted">
                      ▾
                    </div>
                  </div>
                </Field>
              </>
            )}

            <Field label={t("login.fullNameLabel")}>
              <input
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder={t("login.fullNamePlaceholder")}
                className="h-9 rounded border border-border bg-bg-surface-raised px-3 text-sm text-text-primary placeholder:text-text-muted transition-colors focus:border-accent focus:outline-none"
              />
            </Field>

            <Field label={t("login.emailLabel")}>
              <input
                required
                type="email"
                dir="ltr"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={t("login.emailPlaceholder")}
                className="h-9 rounded border border-border bg-bg-surface-raised px-3 text-sm text-text-primary placeholder:text-text-muted transition-colors focus:border-accent focus:outline-none"
              />
            </Field>

            <Field label={t("login.passwordLabel")}>
              <input
                required
                type="password"
                dir="ltr"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="h-9 rounded border border-border bg-bg-surface-raised px-3 text-sm text-text-primary placeholder:text-text-muted transition-colors focus:border-accent focus:outline-none"
              />
            </Field>

            {error && (
              <div className="flex items-start gap-2 rounded border border-danger/30 bg-danger/10 p-2.5 text-xs leading-relaxed text-danger">
                <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={busy}
              className="mt-2 inline-flex h-9 items-center justify-center rounded border border-accent bg-accent px-4 font-mono text-xs font-medium text-accent-text transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busy ? t("common.working") : t("companyRegister.submit")}
            </button>
          </form>

          {/* Navigation link */}
          <div className="mt-5 border-t border-border pt-4">
            <Link
              href="/login"
              className="block w-full text-center font-mono text-xs text-text-muted transition-colors hover:text-text-secondary"
            >
              ← {t("companyRegister.backToLogin")}
            </Link>
          </div>
        </div>

        {/* Footer info */}
        <div className="mt-6 flex items-center justify-between px-2 font-mono text-[10px] text-text-muted">
          <span>SPEC // REG_ORG_V1</span>
          <span>ENTERPRISE_ONBOARDING</span>
        </div>
      </div>
    </main>
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
