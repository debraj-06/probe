import { agentMeta, classificationStyle, confidenceLabel, severityStyle } from "../../lib/format";
import { evidenceUrl } from "../../lib/api";
import type { FindingDetail as FindingDetailType } from "../../types";
import { Button, ConfidenceMeter, SeverityBadge } from "../ui";

function ScreenshotGrid({ finding }: { finding: FindingDetailType }) {
  const shots = finding.evidence.filter((item) => item.kind === "screenshot" && item.url);
  if (shots.length === 0) return null;
  return (
    <section>
      <h3 className="text-[11px] font-semibold tracking-wider text-slate-500 uppercase">
        Evidence — screenshots
      </h3>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        {shots.map((shot) => (
          <a
            key={shot.id}
            href={evidenceUrl(shot.url) ?? "#"}
            target="_blank"
            rel="noreferrer noopener"
            className="group block overflow-hidden rounded-lg border border-ink-700"
          >
            <img
              src={evidenceUrl(shot.url)}
              alt={String(shot.meta?.name ?? "evidence screenshot")}
              className="max-h-56 w-full bg-ink-950 object-contain transition group-hover:opacity-90"
            />
            <p className="border-t border-ink-700 px-2 py-1 font-mono text-[10px] text-slate-600">
              {String(shot.meta?.stage ?? shot.meta?.name ?? "screenshot")}
            </p>
          </a>
        ))}
      </div>
    </section>
  );
}

function EvidenceList({ finding }: { finding: FindingDetailType }) {
  const consoleEntries = finding.evidence.filter((item) => item.kind === "console");
  const networkEntries = finding.evidence.filter((item) => item.kind === "network");
  const timeline = finding.evidence.find((item) => item.kind === "timeline");

  const renderList = (items: unknown[], render: (item: Record<string, unknown>) => string) => {
    const flat = items.flatMap((item) => {
      const entries = (item as { meta?: { entries?: unknown[] } }).meta?.entries;
      return Array.isArray(entries) ? entries : [];
    }) as Array<Record<string, unknown>>;
    if (flat.length === 0) return null;
    return (
      <ul className="mt-2 space-y-1">
        {flat.slice(-8).map((entry, index) => (
          <li
            key={index}
            className="rounded border border-ink-700/70 bg-ink-950/60 px-2 py-1 font-mono text-[11px] text-slate-400"
          >
            {render(entry)}
          </li>
        ))}
      </ul>
    );
  };

  return (
    <div className="space-y-4">
      {consoleEntries.length > 0 ? (
        <section>
          <h3 className="text-[11px] font-semibold tracking-wider text-slate-500 uppercase">
            Console evidence
          </h3>
          {renderList(consoleEntries, (entry) =>
            `[${String(entry.level ?? "error")}] ${String(entry.text ?? "")}`,
          )}
        </section>
      ) : null}

      {networkEntries.length > 0 ? (
        <section>
          <h3 className="text-[11px] font-semibold tracking-wider text-slate-500 uppercase">
            Network evidence
          </h3>
          {renderList(networkEntries, (entry) =>
            `${String(entry.method ?? "?")} ${String(entry.url ?? "")} → ${
              entry.status ?? String(entry.failure ?? "failed")
            } (${Math.round(Number(entry.duration_ms ?? 0))}ms)`,
          )}
        </section>
      ) : null}

      {timeline ? (
        <section>
          <h3 className="text-[11px] font-semibold tracking-wider text-slate-500 uppercase">
            Reproduction timeline
          </h3>
          <ol className="mt-2 space-y-1">
            {((timeline.meta?.events ?? []) as Array<Record<string, unknown>>).map((entry, index) => (
              <li
                key={index}
                className="flex items-center gap-2 rounded border border-ink-700/70 bg-ink-950/60 px-2 py-1 font-mono text-[11px]"
              >
                <span className="text-slate-500">#{String(entry.attempt ?? index + 1)}</span>
                <span className="text-slate-300">{String(entry.action ?? "")}</span>
                <span className="ml-auto text-slate-600">
                  {Math.round(Number(entry.duration_ms ?? 0))}ms
                </span>
                <span
                  className={
                    entry.recurred ? "text-rose-300" : "text-slate-600"
                  }
                >
                  {entry.recurred ? "reproduced" : "no repro"}
                </span>
              </li>
            ))}
          </ol>
        </section>
      ) : null}
    </div>
  );
}

export default function FindingDetailView({
  finding,
  onClose,
}: {
  finding: FindingDetailType;
  onClose: () => void;
}) {
  const style = severityStyle(finding.severity);
  const classification = classificationStyle(finding.classification);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-ink-950/70 backdrop-blur-sm">
      <div
        className="absolute inset-0"
        onClick={onClose}
        role="presentation"
        aria-label="Close finding"
      />
      <aside className="animate-rise relative flex h-full w-full max-w-2xl flex-col border-l border-ink-700 bg-ink-900/95 shadow-2xl">
        <header className="flex items-start gap-3 border-b border-ink-700 px-5 py-4">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <SeverityBadge severity={finding.severity} />
              <span className={`text-[11px] ${classification.className}`}>
                {classification.icon} {classification.label}
              </span>
              {finding.correlated ? (
                <span className="rounded bg-probe-500/15 px-1.5 py-0.5 text-[10px] font-medium text-probe-300">
                  correlated finding
                </span>
              ) : null}
            </div>
            <h2 className="mt-2 text-lg font-semibold text-slate-100">{finding.title}</h2>
            <p className="mt-1 font-mono text-[11px] text-slate-600">
              {finding.category} · {finding.url ?? "—"} · confidence{" "}
              {confidenceLabel(finding.confidence)}
              {finding.reproduced ? ` · reproduced ${finding.reproduced}` : ""}
            </p>
          </div>
          <Button variant="ghost" onClick={onClose} aria-label="Close">
            ✕
          </Button>
        </header>

        <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-5 py-5">
          <section className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-ink-700 bg-ink-850/60 p-3">
              <h3 className="text-[11px] font-semibold tracking-wider text-slate-500 uppercase">
                Expected
              </h3>
              <p className="mt-1 text-sm text-slate-300">
                {finding.expected || "—"}
              </p>
            </div>
            <div className="rounded-lg border border-ink-700 bg-ink-850/60 p-3">
              <h3 className="text-[11px] font-semibold tracking-wider text-slate-500 uppercase">
                Actual
              </h3>
              <p className="mt-1 text-sm text-slate-300">{finding.actual || "—"}</p>
            </div>
          </section>

          <section>
            <h3 className="text-[11px] font-semibold tracking-wider text-slate-500 uppercase">
              Description
            </h3>
            <p className="mt-1 text-sm leading-relaxed whitespace-pre-line text-slate-300">
              {finding.description || "—"}
            </p>
          </section>

          {finding.contributing_factors.length > 0 || finding.correlation_note ? (
            <section className="rounded-lg border border-probe-500/30 bg-probe-500/5 p-4">
              <h3 className="text-[11px] font-semibold tracking-wider text-probe-300 uppercase">
                Why this is one finding
              </h3>
              {finding.correlation_note ? (
                <p className="mt-1.5 text-sm text-slate-300">{finding.correlation_note}</p>
              ) : null}
              {finding.contributing_factors.length > 0 ? (
                <ul className="mt-2 space-y-1">
                  {finding.contributing_factors.map((factor) => (
                    <li key={factor} className="text-[13px] text-slate-400">
                      • {factor}
                    </li>
                  ))}
                </ul>
              ) : null}
              <div className="mt-3 flex flex-wrap gap-1.5">
                {finding.agents.map((role) => (
                  <span
                    key={role}
                    className={`rounded-md border border-ink-600 bg-ink-800/70 px-2 py-0.5 text-[11px] ${agentMeta(role).color}`}
                  >
                    {agentMeta(role).icon} {agentMeta(role).label}
                  </span>
                ))}
              </div>
            </section>
          ) : null}

          {finding.steps.length > 0 ? (
            <section>
              <h3 className="text-[11px] font-semibold tracking-wider text-slate-500 uppercase">
                Reproduction steps
              </h3>
              <ol className="mt-2 space-y-1.5">
                {finding.steps.map((step, index) => (
                  <li key={`${index}-${step}`} className="flex gap-2.5 text-sm text-slate-300">
                    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-ink-600 font-mono text-[10px] text-slate-500">
                      {index + 1}
                    </span>
                    <span className="font-mono text-[12px]">{step}</span>
                  </li>
                ))}
              </ol>
            </section>
          ) : null}

          <ScreenshotGrid finding={finding} />
          <EvidenceList finding={finding} />

          {finding.recommendation ? (
            <section className="rounded-lg border border-emerald-500/25 bg-emerald-500/5 p-4">
              <h3 className="text-[11px] font-semibold tracking-wider text-emerald-300 uppercase">
                Recommendation
              </h3>
              <p className="mt-1.5 text-sm leading-relaxed text-slate-300">
                {finding.recommendation}
              </p>
            </section>
          ) : null}

          <section className="flex items-center justify-between rounded-lg border border-ink-700 bg-ink-850/60 px-4 py-3">
            <div>
              <p className="text-[11px] tracking-wider text-slate-500 uppercase">Severity</p>
              <p className={`text-sm font-semibold ${style.text}`}>{style.label}</p>
            </div>
            <div>
              <p className="text-[11px] tracking-wider text-slate-500 uppercase">Confidence</p>
              <ConfidenceMeter value={finding.confidence} />
            </div>
          </section>
        </div>
      </aside>
    </div>
  );
}
