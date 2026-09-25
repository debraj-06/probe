import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { browserLabel, llmLabel, useEngineStatus } from "../hooks/useEngine";
import { api } from "../lib/api";
import { DEPTH_LABELS, durationLabel, hostOf, severityStyle, timeAgo } from "../lib/format";
import type { Inspection, Severity } from "../types";
import {
  Button,
  EmptyState,
  Panel,
  SeverityBar,
  SeverityBadge,
  SkeletonRows,
  StatCard,
  StatusPill,
} from "./ui";

const SEVERITIES: Severity[] = ["critical", "high", "medium", "low", "info"];

/** Sum the severity counts out of every report we have. */
function severityTotals(rows: Inspection[]): Record<string, number> {
  const totals: Record<string, number> = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
  for (const row of rows) {
    const report = row.report;
    if (!report) continue;
    for (const key of SEVERITIES) totals[key] += report[key] ?? 0;
  }
  return totals;
}

export default function Dashboard() {
  const [inspections, setInspections] = useState<Inspection[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { health, online } = useEngineStatus();

  useEffect(() => {
    let alive = true;
    const load = () =>
      api
        .inspections()
        .then((rows) => alive && setInspections(rows))
        .catch(
          (err: unknown) =>
            alive && setError(err instanceof Error ? err.message : String(err)),
        );
    void load();
    // Keep a finished run's row up to date without a manual refresh.
    const timer = window.setInterval(load, 5000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, []);

  const rows = inspections ?? [];
  const findings = rows.reduce((total, row) => total + row.finding_count, 0);
  const running = rows.filter((row) => row.status === "running").length;
  const withFindings = rows.filter((row) => row.finding_count > 0).length;
  // Real number of agent runs recorded across all inspections.
  const agentRuns = rows.reduce((total, row) => total + (row.agent_count ?? 0), 0);
  const totals = severityTotals(rows);
  const worst = SEVERITIES.reduce((sum, key) => sum + (totals[key] ?? 0), 0);

  const withReports = rows.filter((row) => (row.report?.top_findings?.length ?? 0) > 0);

  return (
    <div className="h-full overflow-y-auto p-4 sm:p-6">
      <div className="mx-auto max-w-6xl space-y-6">
        {/* hero --------------------------------------------------------- */}
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-slate-100">Inspections</h1>
            <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-slate-500">
              Give PROBE a website. Its AI testers explore it like a QA engineer, a UX
              designer, a real user and a chaos tester — then investigate what they find.
            </p>
          </div>
          <Link to="/new">
            <Button>+ New inspection</Button>
          </Link>
        </div>

        {/* engine strip -------------------------------------------------- */}
        <div className="panel hairline-top flex flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 text-xs">
          <div className="flex items-center gap-2">
            <span
              className={`h-1.5 w-1.5 rounded-full ${online ? "bg-emerald-400" : "bg-rose-500"}`}
            />
            <span className="text-slate-500">Backend</span>
            <span className="font-mono text-slate-300">{online ? "online" : "offline"}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-slate-500">Browser</span>
            <span className="font-mono text-slate-300">
              {browserLabel(health?.browser_mode)}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-slate-500">Decisions</span>
            <span className="font-mono text-slate-300">
              {llmLabel(health?.llm_provider, health?.llm_model)}
            </span>
          </div>
          {health?.active_inspections ? (
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-probe-400" />
              <span className="font-mono text-probe-300">
                {health.active_inspections} active
              </span>
            </div>
          ) : null}
          <p className="ml-auto hidden text-[11px] text-slate-600 lg:block">
            {health?.browser_mode === "playwright"
              ? "real Chromium"
              : "simulator engine — install Chromium for live browsing"}
          </p>
        </div>

        {/* stats --------------------------------------------------------- */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Inspections"
            value={rows.length}
            hint={running > 0 ? `${running} running now` : "none running"}
          />
          <StatCard
            label="Findings"
            value={findings}
            hint="validated by Review AI"
            accent={worst > 0 ? "text-orange-300" : "text-probe-300"}
            bar={worst > 0 ? "bg-orange-400" : "bg-probe-400"}
          >
            <SeverityBar counts={totals} className="mt-2.5" />
          </StatCard>
          <StatCard
            label="Apps with findings"
            value={withFindings}
            hint={rows.length ? `of ${rows.length} inspected` : "nothing inspected yet"}
            accent="text-amber-300"
            bar="bg-amber-400"
          />
          <StatCard
            label="Agent runs"
            value={agentRuns}
            hint="Technical · UX · Chaos · User · Review"
            accent="text-violet-300"
            bar="bg-violet-400"
          />
        </div>

        {/* recent -------------------------------------------------------- */}
        <Panel>
          <header className="flex items-center justify-between border-b border-ink-700/60 px-4 py-3">
            <h2 className="text-[13px] font-semibold tracking-wide text-slate-200 uppercase">
              Recent inspections
            </h2>
            {rows.length > 0 ? (
              <span className="font-mono text-xs text-slate-600">{rows.length} total</span>
            ) : null}
          </header>

          {error && rows.length === 0 ? (
            <EmptyState
              icon="⚠"
              title="Cannot reach the PROBE backend"
              hint={`${error} — start it with: cd services/api && uv run uvicorn app.main:app --port 8000`}
            />
          ) : inspections === null ? (
            <SkeletonRows rows={3} />
          ) : rows.length === 0 ? (
            <EmptyState
              icon="◇"
              title="No inspections yet"
              hint="Start one and watch the agents investigate a live website in real time."
              action={
                <Link to="/new">
                  <Button size="sm">Start your first inspection</Button>
                </Link>
              }
            />
          ) : (
            <ul className="divide-y divide-ink-700/50">
              {rows.map((row) => (
                <li key={row.id}>
                  <Link
                    to={`/inspection/${row.id}`}
                    className="group flex flex-wrap items-center gap-4 px-4 py-3 transition-colors hover:bg-ink-850/60"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-mono text-sm text-slate-200 transition-colors group-hover:text-probe-200">
                        {hostOf(row.url)}
                      </p>
                      <p className="mt-0.5 truncate text-xs text-slate-600">
                        {DEPTH_LABELS[row.depth] ?? row.depth} · {row.focus.join(", ")} ·{" "}
                        {timeAgo(row.created_at)}
                      </p>
                    </div>

                    {row.report ? (
                      <div className="hidden w-28 sm:block">
                        <SeverityBar
                          counts={{
                            critical: row.report.critical,
                            high: row.report.high,
                            medium: row.report.medium,
                            low: row.report.low,
                            info: row.report.info,
                          }}
                        />
                      </div>
                    ) : null}

                    <StatusPill status={row.status} />

                    <div className="w-24 text-right">
                      <p className="font-mono text-sm text-slate-300">{row.finding_count}</p>
                      <p className="text-[11px] text-slate-600">findings</p>
                    </div>
                    <div className="w-20 text-right font-mono text-xs text-slate-500">
                      {durationLabel(row.duration_s)}
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        {/* latest findings ---------------------------------------------- */}
        {withReports.length > 0 ? (
          <Panel>
            <header className="border-b border-ink-700/60 px-4 py-3">
              <h2 className="text-[13px] font-semibold tracking-wide text-slate-200 uppercase">
                Latest findings
              </h2>
            </header>
            <ul className="divide-y divide-ink-700/50">
              {withReports
                .slice(0, 3)
                .flatMap((row) =>
                  (row.report?.top_findings ?? []).slice(0, 3).map((finding) => (
                    <li key={finding.id}>
                      <Link
                        to={`/inspection/${row.id}`}
                        className="group flex items-center gap-3 px-4 py-2.5 transition-colors hover:bg-ink-850/60"
                      >
                        <span
                          className={`h-2 w-2 shrink-0 rounded-full ${severityStyle(finding.severity).dot}`}
                        />
                        <span className="min-w-0 flex-1 truncate text-sm text-slate-300 transition-colors group-hover:text-slate-100">
                          {finding.title}
                        </span>
                        {finding.correlated ? (
                          <span
                            className="hidden shrink-0 rounded bg-probe-500/15 px-1.5 py-0.5 text-[10px] font-medium text-probe-300 sm:block"
                            title="Correlated across multiple agent perspectives"
                          >
                            correlated
                          </span>
                        ) : null}
                        <span className="hidden font-mono text-[11px] text-slate-600 sm:block">
                          {hostOf(row.url)}
                        </span>
                        <span className="hidden shrink-0 sm:block">
                          <SeverityBadge severity={finding.severity} />
                        </span>
                      </Link>
                    </li>
                  )),
                )}
            </ul>
          </Panel>
        ) : null}
      </div>
    </div>
  );
}
