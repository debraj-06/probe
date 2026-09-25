import type { ButtonHTMLAttributes, ReactNode } from "react";

import { agentMeta, confidenceLabel, severityStyle, STATUS_STYLES } from "../lib/format";
import type { InspectionStatus, Severity } from "../types";

// ---------------------------------------------------------------------------
export function Panel({
  children,
  className = "",
  raised = false,
}: {
  children: ReactNode;
  className?: string;
  raised?: boolean;
}) {
  return (
    <section className={`${raised ? "panel-raised" : "panel"} hairline-top ${className}`}>
      {children}
    </section>
  );
}

export function PanelHeader({
  title,
  subtitle,
  right,
  icon,
}: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <header className="flex items-start justify-between gap-3 border-b border-ink-700/60 px-4 py-3">
      <div className="flex min-w-0 items-start gap-2.5">
        {icon ? <span className="mt-0.5 text-sm text-slate-500">{icon}</span> : null}
        <div className="min-w-0">
          <h2 className="text-[13px] font-semibold tracking-wide text-slate-200 uppercase">
            {title}
          </h2>
          {subtitle ? (
            <p className="mt-0.5 truncate text-xs text-slate-500">{subtitle}</p>
          ) : null}
        </div>
      </div>
      {right ? <div className="flex shrink-0 items-center gap-2">{right}</div> : null}
    </header>
  );
}

// ---------------------------------------------------------------------------
type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost" | "danger" | "subtle";
  size?: "sm" | "md";
  as?: never;
};

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  ...rest
}: ButtonProps) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all duration-150 " +
    "disabled:cursor-not-allowed disabled:opacity-45 disabled:shadow-none active:translate-y-px";
  const sizes = {
    sm: "px-2.5 py-1.5 text-xs",
    md: "px-4 py-2 text-sm",
  }[size];
  const styles = {
    primary:
      "bg-gradient-to-b from-probe-400 to-probe-500 text-ink-950 " +
      "shadow-[0_1px_0_rgba(255,255,255,0.25)_inset,0_0_22px_-8px_rgba(34,211,238,0.9)] " +
      "hover:from-probe-300 hover:to-probe-400",
    ghost:
      "border border-ink-600/90 bg-ink-850/50 text-slate-300 " +
      "hover:border-probe-500/55 hover:bg-ink-800/70 hover:text-probe-200",
    danger:
      "border border-rose-500/40 bg-rose-500/8 text-rose-200 hover:bg-rose-500/16 hover:border-rose-500/60",
    subtle: "text-slate-400 hover:bg-ink-800/70 hover:text-slate-200",
  }[variant];
  return <button className={`${base} ${sizes} ${styles} ${className}`} {...rest} />;
}

// ---------------------------------------------------------------------------
export function StatusPill({ status }: { status: InspectionStatus }) {
  const style = STATUS_STYLES[status] ?? STATUS_STYLES.queued;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${style.className}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          status === "running" ? "animate-pulse-dot bg-probe-400" : "bg-current"
        }`}
      />
      {style.label}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: Severity | string }) {
  const style = severityStyle(severity);
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-semibold tracking-wide uppercase ${style.bg} ${style.text}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
      {style.label}
    </span>
  );
}

export function ConfidenceMeter({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2" title={`Confidence ${pct}%`}>
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-ink-700">
        <div
          className="h-full rounded-full bg-gradient-to-r from-probe-600 via-probe-500 to-probe-300 transition-[width] duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="font-mono text-[11px] text-slate-400">{confidenceLabel(value)}</span>
    </div>
  );
}

export function AgentChip({ role, active = false }: { role: string; active?: boolean }) {
  const meta = agentMeta(role);
  return (
    <span
      title={meta.label}
      className={`inline-flex items-center gap-1.5 rounded-md border border-ink-600/80 bg-ink-800/70 px-2 py-0.5 text-[11px] ${
        active ? `ring-1 ${meta.ring}` : ""
      } ${meta.color}`}
    >
      <span aria-hidden>{meta.icon}</span>
      {meta.short}
    </span>
  );
}

/** Small monospace key/value used for metadata rows. */
export function MetaItem({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="text-right">
      <p className="font-mono text-sm text-slate-300">{value}</p>
      <p className="text-[11px] text-slate-600">{label}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
export function StatCard({
  label,
  value,
  hint,
  accent = "text-probe-300",
  bar = "bg-probe-400",
  children,
}: {
  label: string;
  value: string | number;
  hint?: string;
  accent?: string;
  bar?: string;
  children?: ReactNode;
}) {
  return (
    <div className="panel hairline-top relative overflow-hidden px-4 py-3.5 transition-colors duration-200 hover:border-ink-600">
      <span
        aria-hidden
        className={`absolute inset-y-0 left-0 w-0.5 ${bar} opacity-70`}
      />
      <p className="text-[11px] font-medium tracking-wider text-slate-500 uppercase">
        {label}
      </p>
      <p className={`mt-1.5 font-mono text-2xl font-semibold tabular-nums ${accent}`}>
        {value}
      </p>
      {hint ? <p className="mt-0.5 text-xs text-slate-600">{hint}</p> : null}
      {children}
    </div>
  );
}

/** Stacked severity distribution — one glance at how bad a run was. */
export function SeverityBar({
  counts,
  className = "",
}: {
  counts: Record<string, number>;
  className?: string;
}) {
  const order: Severity[] = ["critical", "high", "medium", "low", "info"];
  const total = order.reduce((sum, key) => sum + (counts[key] ?? 0), 0);

  if (total === 0) {
    return (
      <div className={`h-1.5 overflow-hidden rounded-full bg-ink-800 ${className}`}>
        <div className="h-full w-full bg-ink-700" />
      </div>
    );
  }

  return (
    <div
      className={`flex h-1.5 overflow-hidden rounded-full bg-ink-800 ${className}`}
      role="img"
      aria-label={order
        .filter((key) => counts[key])
        .map((key) => `${counts[key]} ${key}`)
        .join(", ")}
    >
      {order.map((key) => {
        const value = counts[key] ?? 0;
        if (!value) return null;
        return (
          <div
            key={key}
            className={`${severityStyle(key).dot} h-full transition-all duration-500`}
            style={{ width: `${(value / total) * 100}%` }}
            title={`${value} ${key}`}
          />
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
export function EmptyState({
  icon = "◇",
  title,
  hint,
  action,
}: {
  icon?: string;
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2.5 px-6 py-12 text-center">
      <span className="flex h-11 w-11 items-center justify-center rounded-xl border border-ink-700 bg-ink-850/70 text-lg text-ink-500">
        {icon}
      </span>
      <p className="text-sm font-medium text-slate-400">{title}</p>
      {hint ? <p className="max-w-sm text-xs leading-relaxed text-slate-600">{hint}</p> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-xs text-slate-500">
      <span className="h-3 w-3 animate-spin rounded-full border-2 border-ink-600 border-t-probe-400" />
      {label}
    </span>
  );
}

/** Skeleton rows used while a list is loading. */
export function SkeletonRows({ rows = 3 }: { rows?: number }) {
  return (
    <ul className="divide-y divide-ink-700/50">
      {Array.from({ length: rows }).map((_, index) => (
        <li key={index} className="flex items-center gap-4 px-4 py-3.5">
          <div className="min-w-0 flex-1 space-y-2">
            <div className="skeleton h-3.5 w-1/3" />
            <div className="skeleton h-2.5 w-1/2" />
          </div>
          <div className="skeleton h-6 w-20 rounded-full" />
          <div className="skeleton h-3.5 w-12" />
        </li>
      ))}
    </ul>
  );
}
