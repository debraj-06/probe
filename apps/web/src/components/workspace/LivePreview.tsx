import { useEffect, useRef, useState } from "react";

import { evidenceUrl } from "../../lib/api";
import { agentMeta } from "../../lib/format";
import type { AgentState } from "../../hooks/useInspectionStream";
import { EmptyState, Spinner } from "../ui";

/**
 * Live browser view: the newest screenshot the agents captured, streamed over
 * the WebSocket (with a polling fallback for the moments in between).
 *
 * Framed as a browser window — traffic lights and a URL bar — so it reads as
 * "this is the page under test" rather than as an arbitrary image.
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
  const [loaded, setLoaded] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const lastAt = useRef(0);

  useEffect(() => {
    if (!screenshot) return;
    const resolved = evidenceUrl(screenshot.url);
    if (!resolved) return;
    setLoaded(false);
    setSource(`${resolved}?t=${screenshot.at}`);
    lastAt.current = screenshot.at;
  }, [screenshot]);

  const activeAgent = Object.values(agents).find((agent) => agent.status === "active");
  const meta = activeAgent ? agentMeta(activeAgent.role) : null;

  // "still alive" heartbeat between captures
  useEffect(() => {
    if (status !== "running") return;
    const timer = window.setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [status, screenshot?.at]);

  useEffect(() => setElapsed(0), [screenshot?.at]);

  return (
    <>
      {/* browser chrome ------------------------------------------------- */}
      <div className="flex items-center gap-3 border-b border-ink-700/60 bg-ink-875/60 px-3 py-2">
        <span className="flex shrink-0 gap-1.5" aria-hidden>
          <span className="h-2.5 w-2.5 rounded-full bg-rose-500/60" />
          <span className="h-2.5 w-2.5 rounded-full bg-amber-400/60" />
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/60" />
        </span>

        <div className="flex min-w-0 flex-1 items-center gap-2 rounded-md border border-ink-700 bg-ink-950/70 px-2.5 py-1">
          <span
            className={`shrink-0 text-[10px] ${
              status === "running" ? "text-probe-400" : "text-slate-600"
            }`}
            aria-hidden
          >
            {status === "running" ? "●" : "🔒"}
          </span>
          <span className="truncate font-mono text-[11px] text-slate-500">{url}</span>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {activeAgent ? (
            <span
              className={`hidden items-center gap-1.5 rounded-full border border-ink-700 bg-ink-900/70 px-2 py-0.5 text-[11px] sm:flex ${meta?.color}`}
              title={`${meta?.label} is driving the browser`}
            >
              <span aria-hidden>{meta?.icon}</span>
              {meta?.short}
            </span>
          ) : null}
          {status === "running" ? <Spinner label="streaming" /> : null}
          <a
            href={url}
            target="_blank"
            rel="noreferrer noopener"
            className="rounded-md border border-ink-600 px-2 py-1 text-[11px] text-slate-400 transition-colors hover:border-probe-500/50 hover:text-probe-300"
          >
            open ↗
          </a>
        </div>
      </div>

      {/* viewport -------------------------------------------------------- */}
      <div className="relative min-h-0 flex-1 bg-ink-950/60 p-3">
        {source ? (
          <>
            {!loaded ? <div className="skeleton absolute inset-3 rounded-lg" /> : null}
            <img
              src={source}
              alt="Latest browser capture"
              onLoad={() => setLoaded(true)}
              className={`h-full w-full rounded-lg border border-ink-700 object-contain transition-opacity duration-300 ${
                loaded ? "opacity-100" : "opacity-0"
              }`}
            />
          </>
        ) : (
          <div className="flex h-full items-center justify-center">
            {status === "running" ? (
              <div className="flex flex-col items-center gap-4">
                <div className="radar-sweep relative h-24 w-24 overflow-hidden rounded-full border border-probe-500/25">
                  <span className="absolute inset-[30%] rounded-full border border-probe-500/25" />
                  <span className="absolute inset-[12%] rounded-full border border-probe-500/20" />
                  <span className="absolute top-1/2 left-1/2 h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-probe-400" />
                </div>
                <p className="text-xs text-slate-500">Opening the site…</p>
              </div>
            ) : (
              <EmptyState
                icon="🖥"
                title="Waiting for the first capture"
                hint="As soon as an agent opens the site you will see the live browser view here."
              />
            )}
          </div>
        )}

        {source && status === "running" && elapsed > 3 ? (
          <div className="pointer-events-none absolute inset-x-3 bottom-4 flex justify-center">
            <span className="rounded-full border border-ink-700/70 bg-ink-950/90 px-3 py-1 text-[11px] text-slate-500">
              last capture {elapsed}s ago — agent is working…
            </span>
          </div>
        ) : null}
      </div>
    </>
  );
}
