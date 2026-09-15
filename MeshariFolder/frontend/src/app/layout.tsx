import type { Metadata } from "next";
import "@fontsource/space-grotesk/400.css";
import "@fontsource/space-grotesk/500.css";
import "@fontsource/space-grotesk/600.css";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/500.css";
import "@fontsource/ibm-plex-sans-arabic/400.css";
import "@fontsource/ibm-plex-sans-arabic/500.css";
import "@fontsource/ibm-plex-sans-arabic/600.css";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { ThemeProvider } from "@/lib/theme";
import { LocaleProvider } from "@/lib/i18n/locale";

export const metadata: Metadata = {
  title: "Venv — Virtual Work Environment",
  description:
    "A simulated workplace for recent graduates: a Manager assigns tasks, a Mentor reviews the work, HR tracks growth.",
};

// Applies the graduate's theme AND language to <html> before the first
// paint — has to be a plain blocking <script>, not next/script, for the
// same reason in both cases: it has to run before React (and
// globals.css's [data-theme="light"] / [dir="rtl"] rules) ever draw a
// frame, or the page flashes from the default to the stored choice.
// lib/theme.tsx and lib/i18n/locale.tsx's providers each pick up
// whatever this already set on mount, so there's exactly one source of
// truth per concern, never two competing writes.
//
// Theme falls back to the OS preference on a first visit, dark
// otherwise. Language falls back to the browser's language on a first
// visit (an Arabic-language browser gets Arabic by default), English
// otherwise — after that, whatever the graduate explicitly chose via
// the toggle always wins, on every later visit.
const NO_FLASH_SCRIPT = `(function () {
  try {
    var storedTheme = localStorage.getItem("venv-theme");
    var theme = storedTheme === "light" || storedTheme === "dark"
      ? storedTheme
      : (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
    document.documentElement.setAttribute("data-theme", theme);

    var storedLocale = localStorage.getItem("venv-locale");
    var locale = storedLocale === "en" || storedLocale === "ar"
      ? storedLocale
      : (/^ar\\b/.test(navigator.language || "") ? "ar" : "en");
    document.documentElement.setAttribute("lang", locale);
    document.documentElement.setAttribute("dir", locale === "ar" ? "rtl" : "ltr");
  } catch (e) {}
})();`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // suppressHydrationWarning is scoped to this one element's own
    // attributes only (it doesn't suppress anything deeper in the
    // tree) — needed because NO_FLASH_SCRIPT deliberately sets
    // data-theme/lang/dir on <html> before React hydrates, so server
    // and client legitimately disagree on this element for one frame.
    // Same fix next-themes and similar libraries use for the same
    // reason.
    <html lang="en" dir="ltr" className="h-full antialiased" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: NO_FLASH_SCRIPT }} />
      </head>
      <body className="min-h-full flex flex-col bg-bg-base text-text-primary">
        <ThemeProvider>
          <LocaleProvider>
            <AuthProvider>{children}</AuthProvider>
          </LocaleProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
