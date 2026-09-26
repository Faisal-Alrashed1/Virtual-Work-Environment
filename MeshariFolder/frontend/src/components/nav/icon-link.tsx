import Link from "next/link";
import type { ReactNode } from "react";

/** A small icon button matching theme-toggle.tsx's exact visual contract
 * (h-8 w-8, hairline border, no shadow — DESIGN.md's "flat surfaces"
 * rule) — the shared shape for a header's secondary, infrequent actions,
 * so a page's utility icons read as one tidy cluster instead of a row
 * of differently-sized text pills. */
export function IconLink({
  href,
  label,
  children,
  badge,
}: {
  href: string;
  label: string;
  children: ReactNode;
  badge?: number;
}) {
  return (
    <Link
      href={href}
      aria-label={label}
      title={label}
      className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded border border-border text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
    >
      {children}
      {badge !== undefined && badge > 0 && (
        <span className="absolute -end-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-accent px-1 font-mono text-[9px] text-accent-text">
          {badge}
        </span>
      )}
    </Link>
  );
}
