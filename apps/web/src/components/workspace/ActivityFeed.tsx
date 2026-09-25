import { useEffect, useMemo, useRef, useState } from "react";

import { agentMeta, clockTime } from "../../lib/format";
import type { ProbeEvent } from "../../types";
import { PanelHeader } from "../ui";

const EVENT_ICONS: Record<string, string> = {
  "inspection.created": "＋",
  "inspection.started": "▶",
  "inspection.finished": "■",
  "agents.assigned": "🤖",
  "agent.started": "▶",
  "agent.thinking": "💭",
  "agent.action": "→",
  "agent.suspicion": "⚠",
  "agent.investigating": "🔍",
  "agent.reproducing": "↻",
  "agent.reproduced": "✓",
  "agent.finding": "🐞",
  "agent.finished": "■",
  "agent.error": "✕",
  "browser.navigated": "🌐",
  "browser.screenshot": "📷",
  "review.started": "🧠",
  "review.correlated": "🔗",
  "review.completed": "🧠",
  "finding.created": "🐞",
};

const HIGHLIGHT = new Set([
  "agent.suspicion",
  "agent.investigating",
  "agent.reproduced",
  "agent.finding",
  "review.correlated",
  "finding.created",
]);

const FILTERS = [
  { id: "all", label: "All" },
  { id: "signal", label: "Signal" },
] as const;

type FilterId = (typeof FILTERS)[number]["id"];

export default function ActivityFeed({ events }: { events: ProbeEvent[] }) {
  const scroller = useRef<HTMLDivElement>(null);
  const [filter, setFilter] = useState<FilterId>("all");

  useEffect(() => {
    scroller.current?.scrollTo({ top: 0 });
  }, [events.length]);

  const signalCount = useMemo(
    () => events.filter((event) => HIGHLIGHT.has(event.type)).length,
    [events],
  );

  const visible = filter === "signal" ? events.filter((e) => HIGHLIGHT.has(e.type)) : events;

  return (
    <>
      <PanelHeader
        title="Activity"
        subtitle={`${events.length} event${events.length === 1 ? "" : "s"}`}
        icon="⚡"
        right={
          <div className="flex rounded-lg border border-ink-700 bg-ink-950/60 p-0.5">
            {FILTERS.map((option) => (
              <button
                key={option.id}
                type="button"
                onClick={() => setFilter(option.id)}
                className={`rounded-md px-2 py-0.5 text-[11px] transition-colors ${
                  filter === option.id
                    ? "bg-ink-800 text-probe-300"
                    : "text-slate-500 hover:text-slate-300"
                }`}
              >
                {option.label}
                {option.id === "signal" && signalCount > 0 ? (
                  <span className="ml-1 font-mono text-[10px] text-slate-600">
                    {signalCount}
                  </span>
                ) : null}
              </button>
            ))}
          </div>
        }
      />
      <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto p-2">
        {visible.length === 0 ? (
          <p className="px-2 py-8 text-center text-xs leading-relaxed text-slate-600">
            {events.length === 0
              ? "Events will stream in here the moment the inspection starts."
              : "No signal events yet — suspicions and confirmed findings land here."}
          </p>
        ) : null}

        <ol className="space-y-1">
          {visible.map((event) => {
            const meta = event.agent ? agentMeta(event.agent) : null;
            const highlight = HIGHLIGHT.has(event.type);
            return (
              <li
                key={event.id}
                className={`animate-rise rounded-lg border px-2.5 py-2 transition-colors ${
                  highlight
                    ? "border-probe-500/30 bg-probe-500/6"
                    : "border-transparent bg-ink-850/40 hover:bg-ink-850/70"
                }`}
              >
                <div className="flex items-center gap-1.5">
                  <span aria-hidden className="text-[11px]">
                    {EVENT_ICONS[event.type] ?? "·"}
                  </span>
                  {meta ? (
                    <span className={`text-[11px] font-semibold ${meta.color}`}>
                      {meta.short}
                    </span>
                  ) : (
                    <span className="text-[11px] font-semibold text-slate-500">PROBE</span>
                  )}
                  <span className="ml-auto font-mono text-[10px] tabular-nums text-slate-600">
                    {clockTime(event.ts)}
                  </span>
                </div>
                <p
                  className={`mt-0.5 text-[11px] leading-snug ${
                    highlight ? "text-slate-200" : "text-slate-500"
                  }`}
                >
                  {event.message}
                </p>
              </li>
            );
          })}
        </ol>
      </div>
    </>
  );
}
