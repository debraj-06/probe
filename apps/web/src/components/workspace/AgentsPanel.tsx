import { agentMeta } from "../../lib/format";
import type { ProbeEvent } from "../../types";
import type { AgentState } from "../../hooks/useInspectionStream";
import { PanelHeader } from "../ui";

const ORDER = ["technical", "ux", "chaos", "user", "review"];

function roleOf(role: string): string {
  return role;
}

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

  return (
    <>
      <PanelHeader title="AI agents" subtitle="what each perspective is doing" />
      <ul className="min-h-0 flex-1 space-y-1.5 overflow-y-auto p-2">
        {roles.length === 0 ? (
          <li className="px-2 py-6 text-center text-xs text-slate-600">
            Waiting for agents to be assigned…
          </li>
        ) : null}

        {roles.map((role) => {
          const state = agents[roleOf(role)];
          const meta = agentMeta(role);
          const active = state?.status === "active";
          const done = state?.status === "done";
          return (
            <li
              key={role}
              className={`rounded-lg border px-2.5 py-2 transition ${
                active
                  ? "border-probe-500/40 bg-probe-500/5"
                  : "border-ink-700/70 bg-ink-850/50"
              }`}
            >
              <div className="flex items-center gap-2">
                <span
                  className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                    active ? "animate-pulse-dot bg-probe-400" : done ? "bg-emerald-400" : "bg-ink-500"
                  }`}
                />
                <span aria-hidden className="text-xs">
                  {meta.icon}
                </span>
                <span className={`text-xs font-semibold ${meta.color}`}>{meta.short}</span>
                {state && state.steps > 0 ? (
                  <span className="ml-auto font-mono text-[10px] text-slate-600">
                    {state.steps} steps
                  </span>
                ) : null}
              </div>

              <p className="mt-1 line-clamp-2 text-[11px] leading-snug text-slate-500">
                {state?.lastMessage ||
                  (active ? "Starting up…" : done ? "Finished." : "Idle.")}
              </p>

              {state && state.discoveries > 0 ? (
                <p className="mt-1 inline-flex rounded bg-orange-500/10 px-1.5 py-0.5 text-[10px] font-medium text-orange-300">
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
