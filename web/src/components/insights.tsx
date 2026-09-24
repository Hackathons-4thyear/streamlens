import type { ReactNode } from "react";

import type {
  DataScope,
  ForecastSummary,
  Measure,
  StreamAlert,
} from "../lib/insights";
import { Card, Notice } from "./ui";

/** Good / Moderate / Poor, with the same colours the rating screen uses. */
export function StatusPill({
  status,
  size = "md",
}: {
  status: string;
  size?: "sm" | "md";
}) {
  const tones: Record<string, string> = {
    GOOD: "bg-[--color-good] text-white",
    MODERATE: "bg-[--color-moderate] text-white",
    POOR: "bg-[--color-poor] text-white",
    UNKNOWN: "bg-slate-200 text-slate-700",
  };
  const labels: Record<string, string> = {
    GOOD: "Good",
    MODERATE: "Moderate",
    POOR: "Poor",
    UNKNOWN: "No data",
  };
  return (
    <span
      className={`inline-block rounded-full font-bold ${
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm"
      } ${tones[status] ?? tones.UNKNOWN}`}
    >
      {labels[status] ?? status}
    </span>
  );
}

/** The "where did this data come from" control. Never silently mixed. */
export function ScopeToggle({
  scope,
  onChange,
  syntheticCount,
  realCount,
}: {
  scope: DataScope;
  onChange: (scope: DataScope) => void;
  syntheticCount?: number;
  realCount?: number;
}) {
  const options: { value: DataScope; label: string }[] = [
    { value: "all", label: "All data" },
    { value: "real", label: "Real only" },
    { value: "demo", label: "Demo only" },
  ];
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-sm font-semibold text-muted">Showing</span>
      <div className="flex rounded-xl border-2 border-line bg-white p-0.5">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            aria-pressed={scope === option.value}
            className={`tap rounded-lg px-3 py-1.5 text-sm font-semibold transition-colors ${
              scope === option.value
                ? "bg-brand text-white"
                : "text-ink hover:text-brand"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
      {scope !== "real" && (syntheticCount ?? 0) > 0 ? (
        <span className="rounded-full border border-amber-700/40 bg-amber-100 px-2.5 py-1 text-xs font-bold tracking-wide text-amber-900 uppercase">
          ● includes demo data
        </span>
      ) : null}
      {realCount !== undefined && syntheticCount !== undefined ? (
        <span className="text-xs text-muted">
          {realCount} real · {syntheticCount} demo
        </span>
      ) : null}
    </div>
  );
}

export function ForecastBar({ forecast }: { forecast: ForecastSummary }) {
  if (!forecast.available) {
    return (
      <Notice tone="warn" title="No forecast">
        {forecast.error}
      </Notice>
    );
  }

  const fetched = forecast.fetched_at
    ? new Date(forecast.fetched_at).toLocaleString()
    : "";
  const hours = Math.round(forecast.age_seconds / 3600);

  return (
    <Card className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <p className="text-sm font-semibold text-ink">
          Next 48 hours: {forecast.rain_mm_48h} mm rain
          {forecast.temp_max_c != null
            ? `, up to ${Math.round(forecast.temp_max_c)} °C`
            : ""}
        </p>
        <p className="text-xs text-muted">{forecast.source}</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {forecast.synthetic ? (
          <span className="rounded-full border border-amber-700/40 bg-amber-100 px-2.5 py-1 text-xs font-bold tracking-wide text-amber-900 uppercase">
            ● demo forecast
          </span>
        ) : null}
        {forecast.stale ? (
          <span className="rounded-full bg-slate-200 px-2.5 py-1 text-xs font-bold text-slate-700">
            Offline copy, {hours} h old
          </span>
        ) : null}
        {fetched ? (
          <span className="text-xs text-muted">Fetched {fetched}</span>
        ) : null}
      </div>
    </Card>
  );
}

const SEVERITY: Record<string, { tone: "danger" | "warn" | "info"; label: string }> = {
  high: { tone: "danger", label: "Worth acting on" },
  medium: { tone: "warn", label: "Worth knowing" },
  low: { tone: "info", label: "For information" },
};

export function AlertCard({ alert }: { alert: StreamAlert }) {
  const severity = SEVERITY[alert.severity] ?? SEVERITY.medium;
  return (
    <Notice tone={severity.tone} title={alert.name}>
      <p className="mb-3">{alert.message}</p>

      <details className="rounded-lg bg-white/60 p-2">
        <summary className="tap cursor-pointer text-sm font-semibold">
          Why this fired — the exact numbers
        </summary>
        <p className="mt-2 text-sm">{alert.why}</p>
        <table className="mt-2 w-full text-left text-sm">
          <thead>
            <tr className="text-xs uppercase">
              <th className="py-1 pr-2">Condition</th>
              <th className="py-1 pr-2">Measured</th>
              <th className="py-1 pr-2">Threshold</th>
              <th className="py-1">Source of the threshold</th>
            </tr>
          </thead>
          <tbody>
            {alert.conditions.map((condition) => (
              <tr key={condition.key} className="align-top">
                <td className="py-1 pr-2 font-mono text-xs">{condition.key}</td>
                <td className="py-1 pr-2 tabular-nums">
                  {condition.value ?? "—"} {condition.unit}
                </td>
                <td className="py-1 pr-2 tabular-nums">
                  {condition.operator} {condition.threshold}
                </td>
                <td className="py-1 text-xs">{condition.source}</td>
              </tr>
            ))}
          </tbody>
        </table>

        {alert.evidence.length > 0 ? (
          <p className="mt-2 text-xs">
            Based on {alert.evidence.length} citizen answer
            {alert.evidence.length === 1 ? "" : "s"}:{" "}
            {alert.evidence
              .slice(0, 4)
              .map((e) => `${e.question_id} = ${e.codes.join("/")}`)
              .join(", ")}
            {alert.evidence.some((e) => e.synthetic) ? " (includes demo data)" : ""}
          </p>
        ) : null}

        {alert.advice_sources.map((source) => (
          <p key={source.source} className="mt-2 text-xs">
            <strong>{source.claim}:</strong> {source.source}
            {source.note ? ` — ${source.note}` : ""}
          </p>
        ))}
      </details>
    </Notice>
  );
}

export function MeasureCard({ measure }: { measure: Measure }) {
  const effortLabel = { low: "Low effort", medium: "Medium effort", high: "Major work" };
  return (
    <li className="rounded-2xl border border-line bg-white p-4">
      <div className="mb-1 flex flex-wrap items-start justify-between gap-2">
        <h4 className="font-semibold text-ink">{measure.name}</h4>
        <div className="flex gap-1">
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-bold ${
              measure.type === "nature-based"
                ? "bg-emerald-100 text-emerald-900"
                : "bg-slate-200 text-slate-700"
            }`}
          >
            {measure.type === "nature-based" ? "Nature-based" : "Structural"}
          </span>
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
            {effortLabel[measure.effort]}
          </span>
        </div>
      </div>

      <p className="mb-2 text-sm text-muted">{measure.plain_language}</p>

      <dl className="mb-2 text-sm">
        <dt className="font-semibold text-muted">For the stream</dt>
        <dd className="mb-1 text-ink">{measure.ecosystem_benefit}</dd>
        {measure.health_cobenefits.length > 0 ? (
          <>
            <dt className="font-semibold text-muted">Possible co-benefits for people</dt>
            <dd className="text-ink">{measure.health_cobenefits.join(", ")}</dd>
          </>
        ) : null}
      </dl>

      {measure.addresses && measure.addresses.length > 0 ? (
        <p className="mb-2 text-xs text-muted">
          Addresses: {measure.addresses.map((a) => a.problem_name).join(", ")}
        </p>
      ) : null}

      <p className="text-xs text-muted">
        Catalogue of measures, section {measure.source.section}, p.{measure.source.page}
        {measure.source.verified ? " ✓" : ""} · {measure.source.licence}
      </p>
    </li>
  );
}

export function Meter({
  value,
  label,
  caption,
}: {
  value: number;
  label: string;
  caption?: ReactNode;
}) {
  const percent = Math.round(value * 100);
  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <span className="text-sm font-semibold text-muted">{label}</span>
        <span className="text-sm font-bold tabular-nums text-ink">{percent}%</span>
      </div>
      <div
        className="h-2.5 w-full overflow-hidden rounded-full bg-slate-200"
        role="img"
        aria-label={`${label}: ${percent} percent`}
      >
        <div
          className={`h-full rounded-full ${
            percent >= 80 ? "bg-[--color-good]" : percent >= 40 ? "bg-brand" : "bg-amber-500"
          }`}
          style={{ width: `${Math.max(percent, 2)}%` }}
        />
      </div>
      {caption ? <p className="mt-1 text-xs text-muted">{caption}</p> : null}
    </div>
  );
}
