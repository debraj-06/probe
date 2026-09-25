import { useEffect, useRef, useState } from "react";

import { evidenceUrl } from "../../lib/api";
import { agentMeta } from "../../lib/format";
import type { AgentState } from "../../hooks/useInspectionStream";
import { EmptyState, PanelHeader, Spinner } from "../ui";

/**
 * Live browser view: the newest screenshot the agents captured, streamed over
 * the WebSocket (with a polling fallback for the moments in between).
 */
export default function LivePreview({
  screenshot,
  status,
  url,
  agents,
}: {
  screenshot: { url: string; at: number } | null;
  status: string;
  url: string;
  agents: Record<string, AgentState>;
}) {
  const [source, setSource] = useState<string | undefined>(undefined);
  const lastAt = useRef(0);

  useEffect(() => {
    if (!screenshot) return;
    const resolved = evidenceUrl(screenshot.url);
    if (!resolved) return;
    setSource(`${resolved}?t=${screenshot.at}`);
    lastAt.current = screenshot.at;
  }, [screenshot]);

  // while running, the parent hook polls the REST detail every few seconds, so
  // the newest screenshot also arrives through that channel
  const activeAgent = Object.values(agents).find((agent) => agent.status === "active");
  const meta = activeAgent ? agentMeta(activeAgent.role) : null;
  const [elapsed, setElapsed] = useState(0);

  // gentle "still alive" indicator between captures
  useEffect(() => {
    if (status !== "running") return;
    const timer = window.setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [status, screenshot?.at]);

  useEffect(() => setElapsed(0), [screenshot?.at]);

  return (
    <>
      <PanelHeader
        title="Live website"
        subtitle={activeAgent ? `${meta?.label ?? "Agent"} is driving the browser` : url}
        right={
          <div className="flex items-center gap-2">
            {status === "running" ? <Spinner label="streaming" /> : null}
            <a
              href={url}
              target="_blank"
              rel="noreferrer noopener"
              className="rounded-md border border-ink-600 px-2 py-1 text-[11px] text-slate-400 transition hover:border-probe-500/50 hover:text-probe-300"
            >
              open ↗
            </a>
          </div>
        }
      />

      <div className="relative min-h-0 flex-1 bg-ink-950/60 p-3">
        {source ? (
          <img
            src={source}
            alt="Latest browser capture"
            className="h-full w-full rounded-lg border border-ink-700 object-contain"
          />
        ) : (
          <EmptyState
            icon="🖥"
            title="Waiting for the first capture"
            hint="As soon as an agent opens the site you will see the live browser view here."
          />
        )}

        {source && status === "running" && elapsed > 3 ? (
          <div className="pointer-events-none absolute inset-x-3 bottom-4 flex justify-center">
            <span className="rounded-full bg-ink-950/85 px-3 py-1 text-[11px] text-slate-500">
              last capture {elapsed}s ago — agent is working…
            </span>
          </div>
        ) : null}
      </div>
    </>
  );
}
