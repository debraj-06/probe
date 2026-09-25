import { useEffect, useState } from "react";

import { api } from "../../lib/api";
import { agentMeta, classificationStyle, severityStyle } from "../../lib/format";
import type { ReportResponse } from "../../types";
import { EmptyState, PanelHeader, Spinner } from "../ui";

export default function FinalReport({ inspectionId }: { inspectionId: string }) {
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .report(inspectionId)
      .then((result) => alive && setReport(result))
      .catch((err: unknown) =>
        alive && setError(err instanceof Error ? err.message : String(err)),
      );
    return () => {
      alive = false;
    };
  }, [inspectionId]);

  if (error) {
    return (
      <>
        <PanelHeader title="Final report" />
        <EmptyState icon="⚠" title="Report unavailable" hint={error} />
      </>
    );
  }

  if (!report) {
    return (
      <>
        <PanelHeader title="Final report" />
        <div className="flex items-center justify-center py-10">
          <Spinner label="Review AI is assembling the report…" />
        </div>
      </>
    );
  }

  const counts: Array<[string, number, string]> = [
    ["Critical", report.critical, "bg-rose-500"],
    ["High", report.high, "bg-orange-500"],
    ["Medium", report.medium, "bg-amber-400"],
    ["Low", report.low, "bg-sky-400"],
    ["Info", report.info, "bg-slate-400"],
  ];

  return (
    <>
      <PanelHeader
        title="Final report"
        subtitle={`${report.application} · ${report.inspection} inspection · ${report.duration} · ${report.agent_count} agents · ${report.browser}`}
        right={
          report.correlated > 0 ? (
            <span className="rounded bg-probe-500/15 px-2 py-0.5 text-[11px] text-probe-300">
              {report.correlated} correlated
            </span>
          ) : null
        }
      />

      <div className="grid gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-4">
          {report.summary ? (
            <p className="rounded-lg border border-ink-700 bg-ink-850/60 p-4 text-sm leading-relaxed text-slate-300">
              {report.summary}
            </p>
          ) : null}

          <div className="grid grid-cols-5 gap-2">
            {counts.map(([label, value, dot]) => (
              <div
                key={label}
                className="rounded-lg border border-ink-700 bg-ink-850/50 px-3 py-2 text-center"
              >
                <span className={`mx-auto block h-1.5 w-6 rounded-full ${dot}`} />
                <p className="mt-1.5 font-mono text-xl font-semibold text-slate-200">{value}</p>
                <p className="text-[10px] tracking-wider text-slate-600 uppercase">{label}</p>
              </div>
            ))}
          </div>

          <div>
            <h3 className="text-[11px] font-semibold tracking-wider text-slate-500 uppercase">
              Findings by category
            </h3>
            <div className="mt-2 flex flex-wrap gap-2">
              {Object.entries(report.by_category).map(([category, count]) => (
                <span
                  key={category}
                  className="rounded-md border border-ink-600 bg-ink-850/60 px-2.5 py-1 text-xs text-slate-300"
                >
                  {category} <span className="font-mono text-slate-500">×{count}</span>
                </span>
              ))}
              {Object.keys(report.by_category).length === 0 ? (
                <span className="text-xs text-slate-600">No categories — no findings.</span>
              ) : null}
            </div>
          </div>

          <div>
            <h3 className="text-[11px] font-semibold tracking-wider text-slate-500 uppercase">
              All findings
            </h3>
            <ul className="mt-2 divide-y divide-ink-700/60">
              {report.items.map((finding) => {
                const style = severityStyle(finding.severity);
                const classification = classificationStyle(finding.classification);
                return (
                  <li key={finding.id} className="flex items-start gap-3 py-2.5">
                    <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${style.dot}`} />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-slate-200">{finding.title}</p>
                      <p className="mt-0.5 text-[11px] text-slate-600">
                        <span className={classification.className}>
                          {classification.icon} {classification.label}
                        </span>
                        {" · "}
                        {finding.category}
                        {finding.reproduced ? ` · reproduced ${finding.reproduced}` : ""}
                        {finding.correlated ? " · correlated" : ""}
                      </p>
                    </div>
                    <span className="flex shrink-0 gap-0.5">
                      {finding.agents.map((role) => (
                        <span key={role} title={agentMeta(role).label}>
                          {agentMeta(role).icon}
                        </span>
                      ))}
                    </span>
                  </li>
                );
              })}
              {report.items.length === 0 ? (
                <li className="py-6 text-center text-xs text-slate-600">
                  The agents explored the application and found nothing they could evidence.
                </li>
              ) : null}
            </ul>
          </div>
        </div>

        <div className="space-y-3">
          <h3 className="text-[11px] font-semibold tracking-wider text-slate-500 uppercase">
            Agents
          </h3>
          <ul className="space-y-2">
            {report.agents.map((agent) => (
              <li
                key={agent.role}
                className="rounded-lg border border-ink-700 bg-ink-850/50 px-3 py-2"
              >
                <div className="flex items-center gap-2">
                  <span aria-hidden>{agentMeta(agent.role).icon}</span>
                  <span className={`text-xs font-semibold ${agentMeta(agent.role).color}`}>
                    {agent.label}
                  </span>
                  <span className="ml-auto font-mono text-[11px] text-slate-500">
                    {agent.discoveries} disc.
                  </span>
                </div>
                <p className="mt-1 text-[11px] leading-snug text-slate-600">{agent.goal}</p>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </>
  );
}
