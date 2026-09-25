import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../lib/api";
import type { Depth, FocusArea, InspectionCreate } from "../types";
import { Button, Panel } from "./ui";

const DEPTHS: Array<{ value: Depth; label: string; hint: string }> = [
  { value: "quick", label: "Quick", hint: "8 actions per agent — smoke the surface" },
  { value: "balanced", label: "Balanced", hint: "16 actions per agent — the default" },
  { value: "deep", label: "Deep", hint: "28 actions per agent — real investigation" },
  { value: "extreme", label: "Extreme", hint: "45 actions per agent — exhaustive" },
];

const FOCUS: Array<{ value: FocusArea; label: string; icon: string; hint: string }> = [
  { value: "technical", label: "Technical", icon: "🔧", hint: "Functional & technical defects" },
  { value: "ux", label: "UX/UI", icon: "🎨", hint: "Usability & interface quality" },
  { value: "chaos", label: "Chaos", icon: "💥", hint: "Try to break the application" },
  { value: "user", label: "User behavior", icon: "🧭", hint: "Realistic user journeys" },
];

const SUGGESTIONS = [
  "https://demoshop.local",
  "http://localhost:5174",
  "https://example.com",
];

export default function NewInspection() {
  const navigate = useNavigate();
  const [url, setUrl] = useState("https://demoshop.local");
  const [depth, setDepth] = useState<Depth>("deep");
  const [focus, setFocus] = useState<FocusArea[]>(["technical", "ux", "chaos", "user"]);
  const [goals, setGoals] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleFocus = (value: FocusArea) => {
    setFocus((current) =>
      current.includes(value)
        ? current.filter((item) => item !== value)
        : [...current, value],
    );
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    const payload: InspectionCreate = {
      url,
      depth,
      focus: focus.length ? focus : ["technical", "ux", "chaos", "user"],
      goals: goals
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
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
    <div className="h-full overflow-y-auto p-6">
      <form onSubmit={submit} className="mx-auto max-w-3xl space-y-6">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100">New inspection</h1>
          <p className="mt-1 text-sm text-slate-500">
            PROBE launches the site, explores it autonomously and investigates anything that
            looks wrong. No test scripts required.
          </p>
        </div>

        <Panel className="p-5">
          <label className="block text-[13px] font-medium text-slate-300" htmlFor="url">
            Website URL
          </label>
          <input
            id="url"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://example.com"
            required
            className="mt-2 w-full rounded-lg border border-ink-600 bg-ink-950/80 px-3 py-2.5 font-mono text-sm text-slate-100 placeholder:text-slate-600 focus:border-probe-500/70 focus:outline-none"
          />
          <div className="mt-2 flex flex-wrap gap-2">
            {SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => setUrl(suggestion)}
                className="rounded-md border border-ink-700 px-2 py-1 font-mono text-[11px] text-slate-500 transition hover:border-probe-500/50 hover:text-probe-300"
              >
                {suggestion}
              </button>
            ))}
          </div>
        </Panel>

        <Panel className="p-5">
          <p className="text-[13px] font-medium text-slate-300">Inspection depth</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {DEPTHS.map((option) => (
              <label
                key={option.value}
                className={`flex cursor-pointer gap-3 rounded-lg border p-3 transition ${
                  depth === option.value
                    ? "border-probe-500/60 bg-probe-500/10"
                    : "border-ink-700 hover:border-ink-600"
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
                <span>
                  <span className="block text-sm font-medium text-slate-200">
                    {option.label}
                  </span>
                  <span className="block text-xs text-slate-500">{option.hint}</span>
                </span>
              </label>
            ))}
          </div>
        </Panel>

        <Panel className="p-5">
          <p className="text-[13px] font-medium text-slate-300">Testing focus</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {FOCUS.map((option) => {
              const checked = focus.includes(option.value);
              return (
                <label
                  key={option.value}
                  className={`flex cursor-pointer gap-3 rounded-lg border p-3 transition ${
                    checked
                      ? "border-probe-500/60 bg-probe-500/10"
                      : "border-ink-700 hover:border-ink-600"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleFocus(option.value)}
                    className="mt-1 accent-cyan-400"
                  />
                  <span>
                    <span className="block text-sm font-medium text-slate-200">
                      <span aria-hidden className="mr-1.5">
                        {option.icon}
                      </span>
                      {option.label}
                    </span>
                    <span className="block text-xs text-slate-500">{option.hint}</span>
                  </span>
                </label>
              );
            })}
          </div>
        </Panel>

        <Panel className="p-5">
          <label className="block text-[13px] font-medium text-slate-300" htmlFor="goals">
            Optional user goals{" "}
            <span className="font-normal text-slate-600">
              — guidance, not a test script
            </span>
          </label>
          <textarea
            id="goals"
            value={goals}
            onChange={(event) => setGoals(event.target.value)}
            rows={3}
            placeholder={"Find a product and complete checkout"}
            className="mt-2 w-full resize-none rounded-lg border border-ink-600 bg-ink-950/80 px-3 py-2.5 text-sm text-slate-100 placeholder:text-slate-600 focus:border-probe-500/70 focus:outline-none"
          />
          <p className="mt-2 text-xs text-slate-600">
            The User Behavior AI decides for itself how to reach the goal.
          </p>
        </Panel>

        {error ? (
          <p className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
            {error}
          </p>
        ) : null}

        <div className="flex items-center gap-3">
          <Button type="submit" disabled={submitting || !url.trim()}>
            {submitting ? "Launching…" : "Start inspection"}
          </Button>
          <button
            type="button"
            onClick={() => navigate("/")}
            className="text-sm text-slate-500 transition hover:text-slate-300"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
