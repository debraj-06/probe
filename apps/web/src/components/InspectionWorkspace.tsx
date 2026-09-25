import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { api } from "../lib/api";
import { durationLabel, hostOf } from "../lib/format";
import { useInspectionStream } from "../hooks/useInspectionStream";
import type { FindingDetail } from "../types";
import ActivityFeed from "./workspace/ActivityFeed";
import AgentsPanel from "./workspace/AgentsPanel";
import FinalReport from "./workspace/FinalReport";
import FindingDetailView from "./workspace/FindingDetail";
import FindingsFeed from "./workspace/FindingsFeed";
import LivePreview from "./workspace/LivePreview";
import { Button, EmptyState, Panel, Spinner, StatusPill } from "./ui";

export default function InspectionWorkspace() {
  const { id } = useParams<{ id: string }>();
  const stream = useInspectionStream(id);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<FindingDetail | null>(null);
  const [stopping, setStopping] = useState(false);

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
    try {
      await api.stopInspection(id);
      await stream.refresh();
    } finally {
      setStopping(false);
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
        />
      </div>
    );
  }

  const { inspection } = stream;

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* header ---------------------------------------------------------- */}
      <header className="flex flex-wrap items-center gap-3 border-b border-ink-700/70 bg-ink-950/60 px-5 py-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h1 className="truncate font-mono text-sm text-slate-100">
              {hostOf(inspection.url)}
            </h1>
            <StatusPill status={stream.status} />
            {stream.status === "running" ? (
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
          <div className="text-right">
            <p className="font-mono text-sm text-slate-300">
              {durationLabel(inspection.duration_s)}
            </p>
            <p className="text-[11px] text-slate-600">duration</p>
          </div>
          <div className="text-right">
            <p className="font-mono text-sm text-slate-300">{findings.length}</p>
            <p className="text-[11px] text-slate-600">findings</p>
          </div>
          {stream.status === "running" ? (
            <Button variant="danger" onClick={stop} disabled={stopping}>
              {stopping ? "Stopping…" : "Stop"}
            </Button>
          ) : null}
        </div>
      </header>

      {inspection.error ? (
        <p className="border-b border-rose-500/30 bg-rose-500/10 px-5 py-2 text-xs text-rose-300">
          {inspection.error}
        </p>
      ) : null}

      {/* three-column workspace ----------------------------------------- */}
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 p-3 lg:grid-cols-[220px_minmax(0,1fr)_320px]">
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
      {stream.status !== "running" ? (
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
