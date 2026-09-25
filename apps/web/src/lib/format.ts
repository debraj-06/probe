/** Presentation helpers. */

import type { AgentRole, Classification, InspectionStatus, Severity } from "../types";

export const SEVERITY_ORDER: Severity[] = ["critical", "high", "medium", "low", "info"];

export const SEVERITY_STYLES: Record<Severity, { dot: string; text: string; bg: string; label: string }> = {
  critical: {
    dot: "bg-rose-500",
    text: "text-rose-300",
    bg: "bg-rose-500/10 border-rose-500/40",
    label: "Critical",
  },
  high: {
    dot: "bg-orange-500",
    text: "text-orange-300",
    bg: "bg-orange-500/10 border-orange-500/40",
    label: "High",
  },
  medium: {
    dot: "bg-amber-400",
    text: "text-amber-300",
    bg: "bg-amber-400/10 border-amber-400/40",
    label: "Medium",
  },
  low: {
    dot: "bg-sky-400",
    text: "text-sky-300",
    bg: "bg-sky-400/10 border-sky-400/40",
    label: "Low",
  },
  info: {
    dot: "bg-slate-400",
    text: "text-slate-300",
    bg: "bg-slate-400/10 border-slate-400/40",
    label: "Info",
  },
};

export const CLASSIFICATION_STYLES: Record<
  Classification,
  { icon: string; label: string; className: string }
> = {
  confirmed_defect: { icon: "🔴", label: "Confirmed defect", className: "text-rose-300" },
  ux_issue: { icon: "🟡", label: "UX/UI issue", className: "text-amber-300" },
  improvement: { icon: "🔵", label: "Improvement", className: "text-sky-300" },
};

export const AGENT_META: Record<
  AgentRole,
  { label: string; short: string; icon: string; color: string; ring: string }
> = {
  technical: {
    label: "Technical AI",
    short: "Technical",
    icon: "🔧",
    color: "text-sky-300",
    ring: "ring-sky-400/40",
  },
  ux: {
    label: "UX/UI AI",
    short: "UX/UI",
    icon: "🎨",
    color: "text-violet-300",
    ring: "ring-violet-400/40",
  },
  chaos: {
    label: "Chaos AI",
    short: "Chaos",
    icon: "💥",
    color: "text-rose-300",
    ring: "ring-rose-400/40",
  },
  user: {
    label: "User Behavior AI",
    short: "User",
    icon: "🧭",
    color: "text-emerald-300",
    ring: "ring-emerald-400/40",
  },
  review: {
    label: "Review AI",
    short: "Review",
    icon: "🧠",
    color: "text-amber-300",
    ring: "ring-amber-400/40",
  },
};

export const STATUS_STYLES: Record<InspectionStatus, { label: string; className: string }> = {
  queued: { label: "Queued", className: "bg-slate-500/15 text-slate-300 border-slate-500/30" },
  running: { label: "Running", className: "bg-probe-500/15 text-probe-300 border-probe-500/40" },
  completed: { label: "Completed", className: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40" },
  failed: { label: "Failed", className: "bg-rose-500/15 text-rose-300 border-rose-500/40" },
  stopped: { label: "Stopped", className: "bg-amber-500/15 text-amber-300 border-amber-500/40" },
};

export const DEPTH_LABELS: Record<string, string> = {
  quick: "Quick",
  balanced: "Balanced",
  deep: "Deep",
  extreme: "Extreme",
};

export function agentMeta(role: string) {
  return AGENT_META[role as AgentRole] ?? AGENT_META.technical;
}

export function severityStyle(severity: string) {
  return SEVERITY_STYLES[severity as Severity] ?? SEVERITY_STYLES.info;
}

export function classificationStyle(classification: string) {
  return CLASSIFICATION_STYLES[classification as Classification] ?? CLASSIFICATION_STYLES.improvement;
}

export function hostOf(url: string): string {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}

export function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export function clockTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { hour12: false });
}

export function confidenceLabel(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function durationLabel(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${Math.round(seconds % 60)}s`;
}
