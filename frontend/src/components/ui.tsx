/** Shared primitives — the modernized design system's single source of truth
 *  (DESIGN_BRIEF_MODERN_UI.md). Pages inherit the restyle from here; keep them free of
 *  ad-hoc chrome. */
import type { ButtonHTMLAttributes, ReactNode } from "react";

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "danger" | "quiet" }) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-[10px] px-4 py-2.5 text-sm font-semibold " +
    "font-display transition duration-150 ease-out outline-none " +
    "focus-visible:ring-2 focus-visible:ring-nv-red/25 focus-visible:ring-offset-1 " +
    "disabled:cursor-not-allowed disabled:opacity-45";
  const variants = {
    primary: "bg-nv-red text-white hover:bg-nv-red-dark",
    danger: "bg-danger text-white hover:brightness-110",
    ghost: "border border-line bg-surface text-ink hover:bg-canvas-soft",
    quiet: "text-ink-muted hover:text-ink",
  } as const;
  return <button className={`${base} ${variants[variant]} ${className}`} {...props} />;
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-2xl border border-line bg-surface p-5 shadow-[0_1px_2px_rgb(0_0_0/0.04)] ${className}`}
    >
      {children}
    </div>
  );
}

/** Status: dot + text for calm states; a filled pill ONLY for warn/danger, so a filled
 *  shape always means "look at me". */
export function Badge({
  tone = "neutral",
  children,
}: {
  tone?: "neutral" | "ok" | "warn" | "danger" | "info";
  children: ReactNode;
}) {
  if (tone === "warn" || tone === "danger") {
    const filled = {
      warn: "bg-warn-soft text-warn",
      danger: "bg-danger-soft text-danger",
    } as const;
    return (
      <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${filled[tone]}`}>
        {children}
      </span>
    );
  }
  const dots = {
    neutral: "bg-ink-muted/50",
    ok: "bg-ok",
    info: "bg-info",
  } as const;
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-ink">
      <span className={`h-1.5 w-1.5 rounded-full ${dots[tone]}`} />
      {children}
    </span>
  );
}

/** The signature element: every tracking identifier renders as one consistent chip. */
export function Awb({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <span className={`awb-chip ${className}`}>{children}</span>;
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[13px] font-semibold text-ink">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-ink-muted">{hint}</span>}
    </label>
  );
}

export const inputClass =
  "w-full rounded-[10px] border border-line bg-surface px-3.5 py-2.5 text-sm outline-none " +
  "transition duration-150 focus:border-nv-red focus:ring-2 focus:ring-nv-red/20";

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 text-sm text-ink-muted">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-line border-t-nv-red" />
      {label}
    </div>
  );
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-xl border border-danger/25 bg-danger-soft px-4 py-3 text-sm text-danger">
      {children}
    </div>
  );
}

export function EmptyState({ title, body }: { title: string; body?: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-line px-6 py-12 text-center">
      <p className="font-display font-semibold text-ink">{title}</p>
      {body && <p className="mt-1 text-sm text-ink-muted">{body}</p>}
    </div>
  );
}
