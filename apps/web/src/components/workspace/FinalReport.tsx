import { useEffect, useState } from "react";

import { api } from "../../lib/api";
import { exportReportJson, exportReportMarkdown } from "../../lib/export";
import { agentMeta, classificationStyle, severityStyle } from "../../lib/format";
import type { ReportResponse } from "../../types";
import { Button, EmptyState, PanelHeader, SeverityBar, Spinner } from "../ui";

export default function FinalReport({
  inspectionId,
  onMinimize,
}: {
  inspectionId: string;
  onMinimize?: () => void;
}) {
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .report(inspectionId)
      .then((result) => alive && setReport(result))
      .catch(
        (err: unknown) =>
          alive && setError(err instanceof Error ? err.message : String(err)),
      );
    return () => {
      alive = false;
    };
  }, [inspectionId]);

  if (error) {
    return (
      <>
        <PanelHeader
          title="Final report"
          icon="🧠"
          right={
            onMinimize ? (
              <Button size="sm" variant="ghost" onClick={onMinimize}>
                − Minimize
              </Button>
            ) : null
          }
        />
        <EmptyState icon="⚠" title="Report unavailable" hint={error} />
      </>
    );
  }

  if (!report) {
    return (
      <>
        <PanelHeader
          title="Final report"
          icon="🧠"
          right={
            onMinimize ? (
              <Button size="sm" variant="ghost" onClick={onMinimize}>
                − Minimize
              </Button>
            ) : null
          }
        />
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
        icon="🧠"
        subtitle={`${report.application} · ${report.inspection} inspection · ${report.duration} · ${report.agent_count} agents · ${report.browser} · ${report.decision_engine?.mode === "llm" ? `${report.decision_engine.provider} · ${report.decision_engine.model}` : "heuristic policies"}${report.complete ? "" : " · partial report"}`}
        right={
          <div className="flex items-center gap-2">
            {report.correlated > 0 ? (
              <span
                className="hidden rounded bg-probe-500/15 px-2 py-0.5 text-[11px] text-probe-300 sm:inline"
                title="Correlated across multiple agent perspectives by the Review AI"
              >
                {report.correlated} correlated
              </span>
            ) : null}
            {onMinimize ? (
              <Button size="sm" variant="ghost" onClick={onMinimize} title="Minimize the pinned report">
                − Minimize
              </Button>
            ) : null}
            <Button
              size="sm"
              variant="ghost"
              onClick={() => exportReportMarkdown(report)}
              title="Download as Markdown — ready to paste into an issue"
            >
              ↓ Markdown
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => exportReportJson(report)}
              title="Download the raw report JSON"
            >
              ↓ JSON
            </Button>
          </div>
        }
      />

      <div className="grid min-h-0 gap-4 overflow-y-auto p-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-4">
          {!report.complete ? (
            <p className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs leading-relaxed text-amber-200/90">
              This run is incomplete. Findings below are only from agents that finished; do not
              treat this report as full site coverage.
            </p>
          ) : null}
          {report.warnings?.length ? (
            <ul className="space-y-1 rounded-lg border border-ink-700 bg-ink-850/60 p-3 text-xs leading-relaxed text-slate-400">
              {report.warnings.map((warning) => (
                <li key={warning}>• {warning}</li>
              ))}
            </ul>
          ) : null}
          {report.summary ? (
            <p className="rounded-lg border border-ink-700 bg-ink-850/60 p-4 text-sm leading-relaxed text-slate-300">
              {report.summary}
            </p>
          ) : null}

          <div>
            <div className="grid grid-cols-5 gap-2">
              {counts.map(([label, value, dot]) => (
                <div
                  key={label}
                  className="rounded-lg border border-ink-700 bg-ink-850/50 px-3 py-2 text-center transition-colors hover:border-ink-600"
                >
                  <span className={`mx-auto block h-1.5 w-6 rounded-full ${dot}`} />
                  <p className="mt-1.5 font-mono text-xl font-semibold tabular-nums text-slate-200">
                    {value}
                  </p>
                  <p className="text-[10px] tracking-wider text-slate-600 uppercase">{label}</p>
                </div>
              ))}
            </div>
            <SeverityBar
              counts={{
                critical: report.critical,
                high: report.high,
                medium: report.medium,
                low: report.low,
                info: report.info,
              }}
              className="mt-2"
            />
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
            <ul className="mt-2 divide-y divide-ink-700/50">
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
                className="rounded-lg border border-ink-700 bg-ink-850/50 px-3 py-2 transition-colors hover:border-ink-600"
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
