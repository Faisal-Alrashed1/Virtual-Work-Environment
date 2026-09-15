"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ApiError, useAuth } from "@/lib/auth-context";
import { useLocale } from "@/lib/i18n/locale";
import { ThemeToggle } from "@/components/theme-toggle";
import { LocaleToggle } from "@/components/locale-toggle";

export default function LoginPage() {
  const { login, register } = useAuth();
  const router = useRouter();
  const { t } = useLocale();

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
        await login(email, password);
        router.push("/board");
      } else {
        await register(email, password, fullName);
        router.push("/onboarding/cv");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("common.genericError"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="bg-blueprint-grid flex flex-1 flex-col items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <Link
              href="/"
              className="font-mono text-xs text-text-muted hover:text-text-secondary"
            >
              {t("common.venv")}
            </Link>
            <div className="flex items-center gap-2">
              <LocaleToggle />
              <ThemeToggle />
            </div>
          </div>
          <h1 className="mt-3 text-center text-2xl font-medium text-text-primary">
            {mode === "login" ? t("login.signIn") : t("login.createAccount")}
          </h1>
        </div>

        <form
          onSubmit={handleSubmit}
          className="flex flex-col gap-3 rounded border border-border bg-bg-surface p-5"
        >
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
                className="rounded border border-border bg-bg-surface-raised px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-border-strong focus:outline-none"
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
              className="rounded border border-border bg-bg-surface-raised px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-border-strong focus:outline-none"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="font-mono text-[11px] text-text-muted">
              {t("login.passwordLabel")}
            </label>
            <input
              required
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="rounded border border-border bg-bg-surface-raised px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-border-strong focus:outline-none"
            />
          </div>

          {error && <p className="text-sm text-danger">{error}</p>}

          <button
            type="submit"
            disabled={busy}
            className="mt-2 rounded border border-accent bg-accent px-4 py-2 text-sm font-medium text-accent-text transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy
              ? t("common.working")
              : mode === "login"
                ? t("login.submitSignIn")
                : t("login.submitCreateAccount")}
          </button>
        </form>

        <button
          type="button"
          onClick={() => {
            setMode(mode === "login" ? "register" : "login");
            setError(null);
          }}
          className="mt-4 w-full text-center text-xs text-text-muted transition-colors hover:text-text-secondary"
        >
          {mode === "login" ? t("login.switchToRegister") : t("login.switchToLogin")}
        </button>
      </div>
    </main>
  );
}
