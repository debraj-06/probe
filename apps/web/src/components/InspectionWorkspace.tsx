import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { useInspectionStream } from "../hooks/useInspectionStream";
import { api } from "../lib/api";
import { durationLabel, hostOf } from "../lib/format";
import type { FindingDetail } from "../types";
import ActivityFeed from "./workspace/ActivityFeed";
import AgentsPanel from "./workspace/AgentsPanel";
import FinalReport from "./workspace/FinalReport";
import FindingDetailView from "./workspace/FindingDetail";
import FindingsFeed from "./workspace/FindingsFeed";
import LivePreview from "./workspace/LivePreview";
import { Button, EmptyState, MetaItem, Panel, Spinner, StatusPill } from "./ui";

export default function InspectionWorkspace() {
  const { id } = useParams<{ id: string }>();
  const stream = useInspectionStream(id);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<FindingDetail | null>(null);
  const [stopping, setStopping] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const findings = Object.values(stream.findings).sort(
    (a, b) => Number(b.correlated) - Number(a.correlated) || b.confidence - a.confidence,
  );

  useEffect(() => {
    if (!selected) {
      setDetail(null);
      return;
    }
    let alive = true;
    api
      .finding(selected)
      .then((result) => alive && setDetail(result))
      .catch(() => alive && setDetail(null));
    return () => {
      alive = false;
    };
  }, [selected]);

  const stop = useCallback(async () => {
    if (!id) return;
    setStopping(true);
    setActionError(null);
    try {
      await api.stopInspection(id);
      await stream.refresh();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setStopping(false);
    }
  }, [id, stream]);

  /** Re-runs this inspection in place with the settings it was created with. */
  const restart = useCallback(async () => {
    if (!id) return;
    setRestarting(true);
    setActionError(null);
    try {
      await api.restartInspection(id);
      setSelected(null);
      await stream.refresh();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setRestarting(false);
    }
  }, [id, stream]);

  if (stream.loading && !stream.inspection) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="Loading inspection…" />
      </div>
    );
  }

  if (!stream.inspection) {
    return (
      <div className="flex h-full items-center justify-center p-10">
        <EmptyState
          icon="⚠"
          title="Inspection not found"
          hint={stream.error ?? "It may have been created in a different database."}
          action={
            <Link to="/">
              <Button size="sm" variant="ghost">
                Back to dashboard
              </Button>
            </Link>
          }
        />
      </div>
    );
  }

  const { inspection } = stream;
  const running = stream.status === "running";

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* header ---------------------------------------------------------- */}
      <header className="z-10 flex flex-wrap items-center gap-3 border-b border-ink-700/70 bg-ink-950/70 px-4 py-3 backdrop-blur-sm sm:px-5">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Link
              to="/"
              className="rounded-md px-1.5 py-0.5 text-xs text-slate-600 transition-colors hover:bg-ink-850 hover:text-slate-300"
              title="Back to dashboard"
            >
              ←
            </Link>
            <h1 className="truncate font-mono text-sm text-slate-100">
              {hostOf(inspection.url)}
            </h1>
            <StatusPill status={stream.status} />
            {running ? (
              <span className="hidden items-center gap-1.5 text-[11px] text-probe-300 sm:flex">
                <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-probe-400" />
                agents working
              </span>
            ) : null}
          </div>
          <p className="mt-0.5 truncate text-xs text-slate-600">
            {inspection.url} · {inspection.depth} · {inspection.focus.join(", ")}
            {inspection.goals.length ? ` · goal: ${inspection.goals[0]}` : ""}
          </p>
        </div>

        <div className="flex items-center gap-4">
          <MetaItem label="duration" value={durationLabel(inspection.duration_s)} />
          <MetaItem label="findings" value={findings.length} />
          <div className="flex items-center gap-2">
            {running ? (
              <Button variant="danger" size="sm" onClick={stop} disabled={stopping}>
                {stopping ? "Stopping…" : "Stop"}
              </Button>
            ) : (
              <Button variant="ghost" size="sm" onClick={restart} disabled={restarting}>
                {restarting ? "Restarting…" : "↻ Re-run"}
              </Button>
            )}
          </div>
        </div>
      </header>

      {inspection.error ? (
        <p className="border-b border-rose-500/30 bg-rose-500/10 px-5 py-2 text-xs text-rose-300">
          {inspection.error}
        </p>
      ) : null}

      {actionError ? (
        <p className="border-b border-amber-500/30 bg-amber-500/10 px-5 py-2 text-xs text-amber-300">
          {actionError}
        </p>
      ) : null}

      {/* three-column workspace ----------------------------------------- */}
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 p-3 lg:grid-cols-[230px_minmax(0,1fr)_330px]">
        <Panel className="flex min-h-0 flex-col overflow-hidden">
          <AgentsPanel agents={stream.agents} events={stream.events} />
        </Panel>

        <div className="flex min-h-0 flex-col gap-3">
          <Panel className="flex min-h-[280px] flex-1 flex-col overflow-hidden">
            <LivePreview
              screenshot={stream.screenshot}
              status={stream.status}
              url={inspection.url}
              agents={stream.agents}
            />
          </Panel>
          <Panel className="max-h-[38%] min-h-[180px] overflow-hidden">
            <FindingsFeed
              findings={findings}
              onSelect={setSelected}
              selectedId={selected}
              status={stream.status}
            />
          </Panel>
        </div>

        <Panel className="flex min-h-0 flex-col overflow-hidden">
          <ActivityFeed events={stream.events} />
        </Panel>
      </div>

      {/* final report ---------------------------------------------------- */}
      {!running ? (
        <div className="px-3 pb-3">
          <Panel>
            <FinalReport inspectionId={inspection.id} />
          </Panel>
        </div>
      ) : null}

      {detail ? (
        <FindingDetailView finding={detail} onClose={() => setSelected(null)} />
      ) : null}
    </div>
  );
}
