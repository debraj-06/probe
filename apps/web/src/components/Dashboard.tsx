import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../lib/api";
import {
  DEPTH_LABELS,
  durationLabel,
  hostOf,
  severityStyle,
  timeAgo,
} from "../lib/format";
import type { Inspection } from "../types";
import { Button, EmptyState, Panel, SeverityBadge, StatCard, StatusPill } from "./ui";

export default function Dashboard() {
  const [inspections, setInspections] = useState<Inspection[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .inspections()
      .then((rows) => alive && setInspections(rows))
      .catch((err: unknown) =>
        alive && setError(err instanceof Error ? err.message : String(err)),
      );
    return () => {
      alive = false;
    };
  }, []);

  const rows = inspections ?? [];
  const findings = rows.reduce((total, row) => total + row.finding_count, 0);
  const running = rows.filter((row) => row.status === "running").length;
  const critical = rows.filter((row) => row.finding_count > 0).length;

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mx-auto max-w-6xl space-y-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-slate-100">Inspections</h1>
            <p className="mt-1 max-w-2xl text-sm text-slate-500">
              Give PROBE a website. Its AI testers explore it like a QA engineer, a UX
              designer, a real user and a chaos tester — then investigate what they find.
            </p>
          </div>
          <Link to="/new">
            <Button>+ New inspection</Button>
          </Link>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Inspections" value={rows.length} hint={`${running} running now`} />
          <StatCard label="Findings" value={findings} hint="validated by Review AI" />
          <StatCard
            label="With findings"
            value={critical}
            hint="applications that surfaced issues"
            accent="text-orange-300"
          />
          <StatCard
            label="Agents"
            value={5}
            hint="Technical · UX · Chaos · User · Review"
            accent="text-violet-300"
          />
        </div>

        <Panel>
          <header className="flex items-center justify-between border-b border-ink-700/70 px-4 py-3">
            <h2 className="text-[13px] font-semibold tracking-wide text-slate-200 uppercase">
              Recent inspections
            </h2>
            {rows.length > 0 ? (
              <span className="font-mono text-xs text-slate-600">{rows.length} total</span>
            ) : null}
          </header>

          {error ? (
            <EmptyState
              icon="⚠"
              title="Cannot reach the PROBE backend"
              hint={`${error} — start it with: cd services/api && uv run uvicorn app.main:app --port 8000`}
            />
          ) : inspections === null ? (
            <EmptyState icon="◌" title="Loading inspections…" />
          ) : rows.length === 0 ? (
            <EmptyState
              icon="◇"
              title="No inspections yet"
              hint="Start one and watch the agents investigate a live website in real time."
            />
          ) : (
            <ul className="divide-y divide-ink-700/60">
              {rows.map((row) => (
                <li key={row.id}>
                  <Link
                    to={`/inspection/${row.id}`}
                    className="flex flex-wrap items-center gap-4 px-4 py-3 transition hover:bg-ink-850/60"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-mono text-sm text-slate-200">
                        {hostOf(row.url)}
                      </p>
                      <p className="mt-0.5 text-xs text-slate-600">
                        {DEPTH_LABELS[row.depth] ?? row.depth} · {row.focus.join(", ")} ·{" "}
                        {timeAgo(row.created_at)}
                      </p>
                    </div>
                    <StatusPill status={row.status} />
                    <div className="w-28 text-right">
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

        {rows.some((row) => (row.report?.top_findings?.length ?? 0) > 0) ? (
          <Panel>
            <header className="border-b border-ink-700/70 px-4 py-3">
              <h2 className="text-[13px] font-semibold tracking-wide text-slate-200 uppercase">
                Latest findings
              </h2>
            </header>
            <ul className="divide-y divide-ink-700/60">
              {rows
                .filter((row) => (row.report?.top_findings?.length ?? 0) > 0)
                .slice(0, 3)
                .flatMap((row) =>
                  (row.report?.top_findings ?? []).slice(0, 3).map((finding) => (
                    <li key={finding.id}>
                      <Link
                        to={`/inspection/${row.id}`}
                        className="flex items-center gap-3 px-4 py-2.5 transition hover:bg-ink-850/60"
                      >
                        <span
                          className={`h-2 w-2 shrink-0 rounded-full ${severityStyle(finding.severity).dot}`}
                        />
                        <span className="min-w-0 flex-1 truncate text-sm text-slate-300">
                          {finding.title}
                        </span>
                        <span className="hidden font-mono text-[11px] text-slate-600 sm:block">
                          {hostOf(row.url)}
                        </span>
                        <span className="hidden sm:block">
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
