import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { browserLabel, llmLabel, useEngineStatus } from "../hooks/useEngine";
import { api } from "../lib/api";
import type { Depth, FocusArea, InspectionCreate } from "../types";
import { Button, Panel } from "./ui";

const DEPTHS: Array<{ value: Depth; label: string; hint: string; steps: number }> = [
  { value: "quick", label: "Quick", hint: "Smoke the surface", steps: 8 },
  { value: "balanced", label: "Balanced", hint: "The everyday default", steps: 16 },
  { value: "deep", label: "Deep", hint: "Real investigation", steps: 28 },
  { value: "extreme", label: "Extreme", hint: "Exhaustive crawl", steps: 45 },
];

const FOCUS: Array<{ value: FocusArea; label: string; icon: string; hint: string }> = [
  { value: "technical", label: "Technical", icon: "🔧", hint: "Functional & technical defects" },
  { value: "ux", label: "UX/UI", icon: "🎨", hint: "Usability & interface quality" },
  { value: "chaos", label: "Chaos", icon: "💥", hint: "Try to break the application" },
  { value: "user", label: "User behavior", icon: "🧭", hint: "Realistic user journeys" },
];

const ALL_FOCUS: FocusArea[] = ["technical", "ux", "chaos", "user"];

/** Local DemoShop is offered as an explicit test target, never pre-selected. */
const DEMO_URL = "http://127.0.0.1:5174/";

const SUGGESTIONS = [
  { url: DEMO_URL, label: "DemoShop (planted defects)" },
  { url: "http://127.0.0.1:5174/#/product/1", label: "DemoShop product page" },
  { url: "https://example.com", label: "example.com" },
];

/** Accepts a bare host and adds a scheme, so "example.com" still works. */
function normaliseUrl(raw: string): string {
  const value = raw.trim();
  if (!value) return "";
  return /^https?:\/\//i.test(value) ? value : `https://${value}`;
}

function urlError(raw: string): string | null {
  const value = raw.trim();
  if (!value) return "Enter the URL you want PROBE to investigate.";
  try {
    const parsed = new URL(normaliseUrl(value));
    if (!parsed.hostname.includes(".")) {
      return "That does not look like a reachable host name.";
    }
    return null;
  } catch {
    return "That is not a valid URL.";
  }
}

export default function NewInspection() {
  const navigate = useNavigate();
  const { health } = useEngineStatus();
  const [url, setUrl] = useState("");
  const [depth, setDepth] = useState<Depth>("balanced");
  const [focus, setFocus] = useState<FocusArea[]>(ALL_FOCUS);
  const [goals, setGoals] = useState("");
  const [authorized, setAuthorized] = useState(false);
  const [allowMutations, setAllowMutations] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [touched, setTouched] = useState(false);

  const validation = useMemo(() => urlError(url), [url]);
  const llmReady = health
    ? health.llm_provider !== "none" || health.allow_heuristic_mode
    : true;
  const canSubmit = !validation && authorized && llmReady && !submitting;
  const depthMeta = DEPTHS.find((option) => option.value === depth)!;

  const toggleFocus = (value: FocusArea) => {
    setFocus((current) =>
      current.includes(value) ? current.filter((item) => item !== value) : [...current, value],
    );
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setTouched(true);
    if (validation) return;
    setSubmitting(true);
    setError(null);
    const payload: InspectionCreate = {
      url: normaliseUrl(url),
      depth,
      focus: focus.length ? focus : ALL_FOCUS,
      goals: goals
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
      authorized,
      allow_mutations: allowMutations,
    };
    try {
      const inspection = await api.createInspection(payload);
      navigate(`/inspection/${inspection.id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  };

  return (
    <div className="h-full overflow-y-auto p-4 sm:p-6">
      <form onSubmit={submit} className="mx-auto max-w-3xl space-y-5">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-100">New inspection</h1>
          <p className="mt-1.5 text-sm leading-relaxed text-slate-500">
            PROBE launches the site, explores it autonomously and investigates anything that
            looks wrong. No test scripts required.
          </p>
        </div>

        {/* URL ----------------------------------------------------------- */}
        <Panel className="p-5">
          <label className="block text-[13px] font-medium text-slate-300" htmlFor="url">
            Website URL
          </label>
          <input
            id="url"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            onBlur={() => setTouched(true)}
            placeholder="https://example.com"
            required
            aria-invalid={touched && validation ? true : undefined}
            aria-describedby="url-help"
            className={`mt-2 w-full rounded-lg border bg-ink-950/80 px-3 py-2.5 font-mono text-sm text-slate-100 transition-colors placeholder:text-slate-600 focus:outline-none ${
              touched && validation
                ? "border-rose-500/60 focus:border-rose-400"
                : "border-ink-600 focus:border-probe-500/70"
            }`}
          />
          <p
            id="url-help"
            className={`mt-2 text-xs ${touched && validation ? "text-rose-400" : "text-slate-600"}`}
          >
            {touched && validation
              ? validation
              : "A bare host name is fine — PROBE adds https:// for you."}
          </p>

          <div className="mt-3 flex flex-wrap gap-2">
            {SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion.url}
                type="button"
                onClick={() => {
                  setUrl(suggestion.url);
                  setTouched(false);
                  setError(null);
                }}
                title={suggestion.url}
                className="rounded-md border border-ink-700 px-2 py-1 font-mono text-[11px] text-slate-500 transition-colors hover:border-probe-500/50 hover:text-probe-300"
              >
                {suggestion.label}
              </button>
            ))}
          </div>
        </Panel>

        {/* depth --------------------------------------------------------- */}
        <Panel className="p-5">
          <div className="flex items-baseline justify-between">
            <p className="text-[13px] font-medium text-slate-300">Inspection depth</p>
            <p className="font-mono text-[11px] text-slate-600">
              {depthMeta.steps} actions × {focus.length || ALL_FOCUS.length} agents
            </p>
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {DEPTHS.map((option) => (
              <label
                key={option.value}
                className={`flex cursor-pointer gap-3 rounded-lg border p-3 transition-all duration-150 ${
                  depth === option.value
                    ? "border-probe-500/60 bg-probe-500/10 shadow-[0_0_24px_-12px_rgba(34,211,238,0.8)]"
                    : "border-ink-700 hover:border-ink-600 hover:bg-ink-850/50"
                }`}
              >
                <input
                  type="radio"
                  name="depth"
                  value={option.value}
                  checked={depth === option.value}
                  onChange={() => setDepth(option.value)}
                  className="mt-1 accent-cyan-400"
                />
                <span className="min-w-0">
                  <span className="flex items-center gap-2 text-sm font-medium text-slate-200">
                    {option.label}
                    <span className="rounded bg-ink-800 px-1.5 py-0.5 font-mono text-[10px] text-slate-500">
                      {option.steps}
                    </span>
                  </span>
                  <span className="mt-0.5 block text-xs text-slate-500">{option.hint}</span>
                </span>
              </label>
            ))}
          </div>
        </Panel>

        {/* focus --------------------------------------------------------- */}
        <Panel className="p-5">
          <div className="flex items-baseline justify-between">
            <p className="text-[13px] font-medium text-slate-300">Testing focus</p>
            <button
              type="button"
              onClick={() => setFocus(focus.length === ALL_FOCUS.length ? [] : ALL_FOCUS)}
              className="text-[11px] text-slate-500 transition-colors hover:text-probe-300"
            >
              {focus.length === ALL_FOCUS.length ? "clear all" : "select all"}
            </button>
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {FOCUS.map((option) => {
              const checked = focus.includes(option.value);
              return (
                <label
                  key={option.value}
                  className={`flex cursor-pointer gap-3 rounded-lg border p-3 transition-all duration-150 ${
                    checked
                      ? "border-probe-500/60 bg-probe-500/10"
                      : "border-ink-700 hover:border-ink-600 hover:bg-ink-850/50"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleFocus(option.value)}
                    className="mt-1 accent-cyan-400"
                  />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-slate-200">
                      <span aria-hidden className="mr-1.5">
                        {option.icon}
                      </span>
                      {option.label}
                    </span>
                    <span className="mt-0.5 block text-xs text-slate-500">{option.hint}</span>
                  </span>
                </label>
              );
            })}
          </div>
          {focus.length === 0 ? (
            <p className="mt-2 text-xs text-amber-400/90">
              No focus selected — PROBE will fall back to all four perspectives.
            </p>
          ) : null}
        </Panel>

        {/* goals --------------------------------------------------------- */}
        <Panel className="p-5">
          <label className="block text-[13px] font-medium text-slate-300" htmlFor="goals">
            Optional user goals{" "}
            <span className="font-normal text-slate-600">— guidance, not a test script</span>
          </label>
          <textarea
            id="goals"
            value={goals}
            onChange={(event) => setGoals(event.target.value)}
            rows={3}
            placeholder={"Find a product and complete checkout"}
            className="mt-2 w-full resize-none rounded-lg border border-ink-600 bg-ink-950/80 px-3 py-2.5 text-sm text-slate-100 transition-colors placeholder:text-slate-600 focus:border-probe-500/70 focus:outline-none"
          />
          <p className="mt-2 text-xs text-slate-600">
            One goal per line. The User Behavior AI decides for itself how to reach it.
          </p>
        </Panel>

        {/* permission and safe browsing -------------------------------- */}
        <Panel className="space-y-4 p-5">
          <label className="flex cursor-pointer items-start gap-3 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={authorized}
              onChange={(event) => setAuthorized(event.target.checked)}
              className="mt-1 accent-cyan-400"
              required
            />
            <span>
              I own this website or have explicit permission to test it.
              <span className="mt-1 block text-xs leading-relaxed text-slate-500">
                PROBE opens the live site in Chromium and interacts with its visible controls. Use a
                staging/test environment where possible; automated checks cannot guarantee a
                defect-free result.
              </span>
            </span>
          </label>
          <div className="border-t border-ink-700/70 pt-4">
            <label className="flex cursor-pointer items-start gap-3 text-sm text-slate-300">
              <input
                type="checkbox"
                checked={allowMutations}
                onChange={(event) => setAllowMutations(event.target.checked)}
                className="mt-1 accent-amber-400"
              />
              <span>
                Allow write requests and high-impact actions
                <span className="mt-1 block text-xs leading-relaxed text-slate-500">
                  Off by default: POST, PUT, PATCH, DELETE requests and common payment/delete
                  controls are blocked. Turn this on only for a disposable staging site. It can
                  create or change real data.
                </span>
              </span>
            </label>
          </div>
        </Panel>

        {/* engine note --------------------------------------------------- */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-ink-700/70 bg-ink-900/50 px-4 py-2.5 text-[11px] text-slate-500">
          <span>
            Browser engine:{" "}
            <span className="font-mono text-slate-300">
              {browserLabel(health?.browser_mode)}
            </span>
          </span>
          <span>
            Decisions:{" "}
            <span className="font-mono text-slate-300">
              {llmLabel(health?.llm_provider, health?.llm_model)}
            </span>
          </span>
        </div>
        {health?.llm_provider === "none" ? (
          <p className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-xs leading-relaxed text-amber-200/80">
            No LLM is configured. Live inspections are disabled until you set
            <code className="mx-1 font-mono">PROBE_LLM_PROVIDER</code> and the matching model/API
            settings for all agents and Review AI. For an explicit offline/demo run only, an
            operator can opt in with
            <code className="mx-1 font-mono">PROBE_ALLOW_HEURISTIC_MODE=true</code>.
          </p>
        ) : null}
        {health?.browser_mode === "mock" ? (
          <p className="rounded-lg border border-rose-500/30 bg-rose-500/5 px-4 py-3 text-xs leading-relaxed text-rose-200/80">
            Simulator mode is enabled. It does not visit the URL or produce live-site findings.
            Set <code className="font-mono">PROBE_BROWSER_MODE=playwright</code> for real
            Chromium inspection.
          </p>
        ) : null}

        {error ? (
          <p
            role="alert"
            className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-300"
          >
            {error}
          </p>
        ) : null}

        <div className="sticky bottom-0 flex items-center gap-3 border-t border-ink-700/60 bg-ink-950/85 py-4 backdrop-blur-sm">
          <Button type="submit" disabled={!canSubmit}>
            {submitting ? "Launching…" : "Start inspection"}
          </Button>
          <button
            type="button"
            onClick={() => navigate("/")}
            className="text-sm text-slate-500 transition-colors hover:text-slate-300"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
