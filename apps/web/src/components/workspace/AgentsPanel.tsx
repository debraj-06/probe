import { agentMeta } from "../../lib/format";
import type { ProbeEvent } from "../../types";
import type { AgentState } from "../../hooks/useInspectionStream";
import { PanelHeader } from "../ui";

const ORDER = ["technical", "ux", "chaos", "user", "review"];

const STATE_COPY: Record<string, string> = {
  active: "Working…",
  done: "Finished.",
  idle: "Idle.",
};

export default function AgentsPanel({
  agents,
  events,
}: {
  agents: Record<string, AgentState>;
  events: ProbeEvent[];
}) {
  const present = new Set([
    ...Object.keys(agents),
    ...ORDER.filter((role) => events.some((event) => event.agent === role)),
  ]);
  const roles = ORDER.filter((role) => present.has(role));
  const activeCount = roles.filter((role) => agents[role]?.status === "active").length;

  return (
    <>
      <PanelHeader
        title="AI agents"
        subtitle={
          activeCount > 0
            ? `${activeCount} working now`
            : roles.length > 0
              ? "what each perspective found"
              : "what each perspective is doing"
        }
        icon="🤖"
      />
      <ul className="min-h-0 flex-1 space-y-1.5 overflow-y-auto p-2">
        {roles.length === 0 ? (
          <li className="space-y-2 px-1 py-2">
            {[0, 1, 2, 3].map((index) => (
              <div key={index} className="skeleton h-14 rounded-lg" />
            ))}
          </li>
        ) : null}

        {roles.map((role) => {
          const state = agents[role];
          const meta = agentMeta(role);
          const status = state?.status ?? "idle";
          const active = status === "active";
          const done = status === "done";
          return (
            <li
              key={role}
              className={`rounded-lg border px-2.5 py-2 transition-all duration-200 ${
                active
                  ? "border-probe-500/40 bg-probe-500/6 shadow-[0_0_20px_-12px_rgba(34,211,238,0.9)]"
                  : "border-ink-700/70 bg-ink-850/50"
              }`}
            >
              <div className="flex items-center gap-2">
                <span
                  className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                    active
                      ? "animate-pulse-dot bg-probe-400"
                      : done
                        ? "bg-emerald-400"
                        : "bg-ink-500"
                  }`}
                />
                <span aria-hidden className="text-xs">
                  {meta.icon}
                </span>
                <span className={`text-xs font-semibold ${meta.color}`}>{meta.short}</span>
                {state && state.steps > 0 ? (
                  <span className="ml-auto font-mono text-[10px] tabular-nums text-slate-600">
                    {state.steps} steps
                  </span>
                ) : null}
              </div>

              <p className="mt-1 line-clamp-2 text-[11px] leading-snug text-slate-500">
                {state?.lastMessage || STATE_COPY[status]}
              </p>

              {state && state.discoveries > 0 ? (
                <p className="mt-1.5 inline-flex rounded bg-orange-500/10 px-1.5 py-0.5 text-[10px] font-medium text-orange-300">
                  {state.discoveries} discovery{state.discoveries > 1 ? "ies" : ""}
                </p>
              ) : null}
            </li>
          );
        })}
      </ul>
    </>
  );
}
