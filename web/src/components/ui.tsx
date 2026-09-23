import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-brand text-white hover:bg-brand-dark disabled:bg-slate-300 disabled:text-slate-600",
  secondary:
    "bg-white text-ink border-2 border-line hover:border-brand hover:text-brand disabled:text-slate-400",
  ghost: "bg-transparent text-brand hover:bg-brand-light",
  danger: "bg-white text-[--color-danger-ink] border-2 border-[--color-danger-ink]/40 hover:bg-[--color-danger-bg]",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  full?: boolean;
}

export function Button({
  variant = "primary",
  full = false,
  className = "",
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={`tap inline-flex items-center justify-center gap-2 rounded-xl px-5 py-3 text-base font-semibold transition-colors disabled:cursor-not-allowed ${
        VARIANTS[variant]
      } ${full ? "w-full" : ""} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-2xl border border-line bg-white p-4 shadow-sm ${className}`}
    >
      {children}
    </div>
  );
}

export function Notice({
  tone = "info",
  title,
  children,
}: {
  tone?: "info" | "warn" | "danger" | "good";
  title?: ReactNode;
  children: ReactNode;
}) {
  const tones = {
    info: "bg-brand-light text-brand-dark border-brand/30",
    warn: "bg-[--color-warn-bg] text-[--color-warn-ink] border-[--color-warn-ink]/25",
    danger: "bg-[--color-danger-bg] text-[--color-danger-ink] border-[--color-danger-ink]/25",
    good: "bg-emerald-50 text-emerald-900 border-emerald-600/30",
  } as const;

  return (
    <div className={`rounded-xl border p-3 text-sm ${tones[tone]}`}>
      {title ? <p className="mb-1 font-semibold">{title}</p> : null}
      <div>{children}</div>
    </div>
  );
}

/**
 * The "demo AI (mock)" badge. Shown wherever mock suggestions appear, so the
 * demo is never mistaken for a running vision model.
 */
export function MockBadge({
  label,
  explanation,
}: {
  label: string;
  explanation: string;
}) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full border border-amber-700/40 bg-amber-100 px-2.5 py-1 text-xs font-bold tracking-wide text-amber-900 uppercase"
      title={explanation}
    >
      <span aria-hidden="true">●</span>
      {label}
      <span className="sr-only">. {explanation}</span>
    </span>
  );
}

export function Spinner({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 text-muted" role="status">
      <span
        className="size-5 animate-spin rounded-full border-2 border-line border-t-brand"
        aria-hidden="true"
      />
      <span>{label}</span>
    </div>
  );
}

/** A confidence reading shown as a bar plus a number, never a bare percentage. */
export function ConfidenceBar({
  value,
  label,
}: {
  value: number;
  label: string;
}) {
  const percent = Math.round(value * 100);
  const tone =
    percent >= 75 ? "bg-brand" : percent >= 55 ? "bg-amber-500" : "bg-slate-400";
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs font-medium text-muted">{label}</span>
      <span
        className="h-2 w-16 overflow-hidden rounded-full bg-slate-200"
        role="img"
        aria-label={`${label}: ${percent} percent`}
      >
        <span
          className={`block h-full rounded-full ${tone}`}
          style={{ width: `${percent}%` }}
        />
      </span>
      <span className="text-xs font-semibold tabular-nums text-muted">
        {percent}%
      </span>
    </div>
  );
}
