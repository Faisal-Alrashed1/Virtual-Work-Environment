"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ArrowRight, ShieldCheck, AlertCircle } from "lucide-react";
import { ApiError, useAuth } from "@/lib/auth-context";
import { useLocale } from "@/lib/i18n/locale";
import { ThemeToggle } from "@/components/theme-toggle";
import { LocaleToggle } from "@/components/locale-toggle";

export default function LoginPage() {
  const { login, register } = useAuth();
  const router = useRouter();
  const { t, locale } = useLocale();

  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "login") {
        const authUser = await login(email, password);
        router.push(authUser.accountType === "company" ? "/company" : "/board");
      } else {
        await register(email, password, fullName);
        router.push("/onboarding/cv");
      }
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
    <main className="relative flex min-h-screen flex-col items-center justify-center bg-blueprint-grid px-6 py-12 text-text-primary selection:bg-accent selection:text-accent-text">
      {/* Top utility bar */}
      <header className="fixed inset-x-0 top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-bg-base/80 px-6 backdrop-blur-md">
        <Link
          href="/"
          className="group flex items-center gap-2 font-mono text-xs text-text-muted transition-colors hover:text-text-primary"
        >
          <BackArrow className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5 rtl:group-hover:translate-x-0.5" />
          <span>{t("common.venv")}</span>
          <span className="hidden text-border-strong sm:inline">/</span>
          <span className="hidden text-[10px] text-text-muted sm:inline">
            SYS.ENTRY
          </span>
        </Link>
        <div className="flex items-center gap-2">
          <LocaleToggle className="bg-bg-surface" />
          <ThemeToggle className="bg-bg-surface" />
        </div>
      </header>

      {/* Auth Container */}
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

          {/* Hairline Accent Indicator */}
          <span className="absolute inset-x-0 top-0 h-[2px] bg-accent" />

          {/* Section Header */}
          <div className="border-b border-border pb-4">
            <div className="flex items-center justify-between font-mono text-[10px] uppercase tracking-wider text-text-muted">
              <span className="flex items-center gap-1.5">
                <ShieldCheck className="h-3 w-3 text-accent-ink" />
                SECURITY_CLEARANCE
              </span>
              <span>AUTH_V2</span>
            </div>
            <h1 className="mt-2 text-xl font-medium text-text-primary">
              {mode === "login" ? t("login.signIn") : t("login.createAccount")}
            </h1>
          </div>

          {/* Mode Segmented Switcher */}
          <div className="mt-5 grid grid-cols-2 gap-1 rounded border border-border bg-bg-base p-1 font-mono text-xs">
            <button
              type="button"
              onClick={() => {
                setMode("login");
                setError(null);
              }}
              className={`rounded px-3 py-1.5 transition-colors ${
                mode === "login"
                  ? "bg-bg-surface text-text-primary font-medium border border-border"
                  : "text-text-muted hover:text-text-secondary"
              }`}
            >
              {t("login.signIn")}
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("register");
                setError(null);
              }}
              className={`rounded px-3 py-1.5 transition-colors ${
                mode === "register"
                  ? "bg-bg-surface text-text-primary font-medium border border-border"
                  : "text-text-muted hover:text-text-secondary"
              }`}
            >
              {t("login.createAccount")}
            </button>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="mt-5 flex flex-col gap-4">
            {mode === "register" && (
              <div className="flex flex-col gap-1.5">
                <label className="font-mono text-[11px] text-text-muted">
                  {t("login.fullNameLabel")}
                </label>
                <input
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder={t("login.fullNamePlaceholder")}
                  className="h-9 rounded border border-border bg-bg-surface-raised px-3 text-sm text-text-primary placeholder:text-text-muted transition-colors focus:border-accent focus:outline-none"
                />
              </div>
            )}

            <div className="flex flex-col gap-1.5">
              <label className="font-mono text-[11px] text-text-muted">
                {t("login.emailLabel")}
              </label>
              <input
                required
                type="email"
                dir="ltr"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={t("login.emailPlaceholder")}
                className="h-9 rounded border border-border bg-bg-surface-raised px-3 text-sm text-text-primary placeholder:text-text-muted transition-colors focus:border-accent focus:outline-none"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="font-mono text-[11px] text-text-muted">
                {t("login.passwordLabel")}
              </label>
              <input
                required
                type="password"
                dir="ltr"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="h-9 rounded border border-border bg-bg-surface-raised px-3 text-sm text-text-primary placeholder:text-text-muted transition-colors focus:border-accent focus:outline-none"
              />
            </div>

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
              {busy
                ? t("common.working")
                : mode === "login"
                  ? t("login.submitSignIn")
                  : t("login.submitCreateAccount")}
            </button>
          </form>

          {/* Alternate Portals / Company Registration */}
          <div className="mt-6 border-t border-border pt-4">
            <Link
              href="/company/register"
              className="block rounded border border-border bg-bg-base/60 p-2.5 text-center font-mono text-xs text-text-secondary transition-colors hover:border-border-strong hover:bg-bg-surface-raised hover:text-text-primary"
            >
              {t("login.registerCompany")} →
            </Link>
          </div>
        </div>

        {/* System Terminal Footer info */}
        <div className="mt-6 flex items-center justify-between px-2 font-mono text-[10px] text-text-muted">
          <span>PORTAL // CLIENT_AUTH</span>
          <span>EST. 2026</span>
        </div>
      </div>
    </main>
  );
}
