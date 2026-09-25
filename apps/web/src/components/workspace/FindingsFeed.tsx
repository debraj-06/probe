import { agentMeta, classificationStyle, confidenceLabel, severityStyle } from "../../lib/format";
import type { Finding } from "../../types";
import { EmptyState, PanelHeader } from "../ui";

export default function FindingsFeed({
  findings,
  onSelect,
  selectedId,
  status,
}: {
  findings: Finding[];
  onSelect: (id: string) => void;
  selectedId: string | null;
  status: string;
}) {
  return (
    <>
      <PanelHeader
        title="Findings"
        subtitle={
          findings.length
            ? `${findings.length} validated by Review AI`
            : status === "running"
              ? "agents are still investigating…"
              : "nothing surfaced"
        }
      />
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {findings.length === 0 ? (
          <EmptyState
            icon="🔍"
            title={status === "running" ? "No findings yet" : "No findings"}
            hint={
              status === "running"
                ? "Suspicious behaviour is investigated and reproduced before it becomes a finding."
                : "The agents explored the application and found nothing they could evidence."
            }
          />
        ) : (
          <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {findings.map((finding) => {
              const style = severityStyle(finding.severity);
              const classification = classificationStyle(finding.classification);
              return (
                <li key={finding.id}>
                  <button
                    type="button"
                    onClick={() => onSelect(finding.id)}
                    className={`w-full rounded-lg border bg-ink-850/60 p-3 text-left transition hover:border-probe-500/50 hover:bg-ink-800/70 ${
                      selectedId === finding.id ? "border-probe-500/70" : "border-ink-700/80"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className={`h-2 w-2 shrink-0 rounded-full ${style.dot}`} />
                      <span className="text-[11px] font-semibold tracking-wide uppercase">
                        <span className={style.text}>{style.label}</span>
                      </span>
                      {finding.correlated ? (
                        <span
                          className="ml-auto rounded bg-probe-500/15 px-1.5 py-0.5 text-[10px] font-medium text-probe-300"
                          title="Correlated across multiple agent perspectives"
                        >
                          correlated
                        </span>
                      ) : null}
                    </div>

                    <p className="mt-1.5 line-clamp-2 text-sm font-medium text-slate-200">
                      {finding.title}
                    </p>

                    <p className="mt-1 text-[11px] text-slate-600">
                      <span className={classification.className}>
                        {classification.icon} {classification.label}
                      </span>
                      {" · "}
                      {finding.category}
                      {finding.reproduced ? ` · reproduced ${finding.reproduced}` : ""}
                    </p>

                    <div className="mt-2 flex items-center justify-between gap-2">
                      <span className="flex flex-wrap gap-1">
                        {finding.agents.map((role) => (
                          <span
                            key={role}
                            className={`text-[10px] ${agentMeta(role).color}`}
                            title={agentMeta(role).label}
                          >
                            {agentMeta(role).icon}
                          </span>
                        ))}
                      </span>
                      <span className="font-mono text-[11px] text-slate-500">
                        {confidenceLabel(finding.confidence)}
                      </span>
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </>
  );
}
