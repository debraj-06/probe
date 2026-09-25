import type { ButtonHTMLAttributes, ReactNode } from "react";

import { agentMeta, confidenceLabel, severityStyle, STATUS_STYLES } from "../lib/format";
import type { InspectionStatus, Severity } from "../types";

// ---------------------------------------------------------------------------
export function Panel({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <section className={`panel ${className}`}>{children}</section>;
}

export function PanelHeader({
  title,
  subtitle,
  right,
}: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
}) {
  return (
    <header className="flex items-start justify-between gap-3 border-b border-ink-700/70 px-4 py-3">
      <div>
        <h2 className="text-[13px] font-semibold tracking-wide text-slate-200 uppercase">
          {title}
        </h2>
        {subtitle ? <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p> : null}
      </div>
      {right}
    </header>
  );
}

// ---------------------------------------------------------------------------
type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost" | "danger";
};

export function Button({ variant = "primary", className = "", ...rest }: ButtonProps) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50";
  const styles = {
    primary:
      "bg-probe-500/90 text-ink-950 hover:bg-probe-400 shadow-[0_0_20px_-6px_rgba(34,211,238,0.8)]",
    ghost: "border border-ink-600 text-slate-300 hover:border-probe-500/60 hover:text-probe-300",
    danger: "border border-rose-500/40 text-rose-300 hover:bg-rose-500/10",
  }[variant];
  return <button className={`${base} ${styles} ${className}`} {...rest} />;
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
          className="h-full rounded-full bg-gradient-to-r from-probe-500 to-probe-300"
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
      className={`inline-flex items-center gap-1.5 rounded-md border border-ink-600/80 bg-ink-800/70 px-2 py-0.5 text-[11px] ${
        active ? `ring-1 ${meta.ring}` : ""
      } ${meta.color}`}
    >
      <span aria-hidden>{meta.icon}</span>
      {meta.short}
    </span>
  );
}

// ---------------------------------------------------------------------------
export function StatCard({
  label,
  value,
  hint,
  accent = "text-probe-300",
}: {
  label: string;
  value: string | number;
  hint?: string;
  accent?: string;
}) {
  return (
    <div className="panel px-4 py-3">
      <p className="text-[11px] font-medium tracking-wider text-slate-500 uppercase">{label}</p>
      <p className={`mt-1 font-mono text-2xl font-semibold ${accent}`}>{value}</p>
      {hint ? <p className="mt-0.5 text-xs text-slate-500">{hint}</p> : null}
    </div>
  );
}

export function EmptyState({
  icon = "◇",
  title,
  hint,
}: {
  icon?: string;
  title: string;
  hint?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      <span className="text-2xl text-ink-500">{icon}</span>
      <p className="text-sm font-medium text-slate-400">{title}</p>
      {hint ? <p className="max-w-sm text-xs text-slate-600">{hint}</p> : null}
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
