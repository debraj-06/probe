import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { api } from "../lib/api";
import type { Health } from "../types";

export interface EngineState {
  health: Health | null;
  /** True once we have heard from the backend at least once. */
  reachable: boolean;
  /** True right now — flips back to false the moment a poll fails. */
  online: boolean;
  error: string | null;
  refresh: () => void;
}

/**
 * Polls `GET /api/health` so the shell can show which engine a run is actually
 * using. This matters because the same inspection means different things
 * depending on the answer: `browser_mode` distinguishes real Chromium from the
 * built-in simulator, and `llm_provider` distinguishes model-driven decisions
 * from the deterministic policies. Neither is visible anywhere else in the UI.
 */
export function useEngine(intervalMs = 10_000): EngineState {
  const [health, setHealth] = useState<Health | null>(null);
  const [online, setOnline] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let alive = true;

    const poll = async () => {
      try {
        const result = await api.health();
        if (!alive) return;
        setHealth(result);
        setOnline(true);
        setError(null);
      } catch (err: unknown) {
        if (!alive) return;
        setOnline(false);
        setError(err instanceof Error ? err.message : String(err));
      }
    };

    void poll();
    const timer = window.setInterval(poll, intervalMs);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [intervalMs, nonce]);

  return {
    health,
    reachable: health !== null,
    online,
    error,
    refresh: () => setNonce((value) => value + 1),
  };
}

/** Human label for the browser engine behind a run. */
export function browserLabel(mode: string | undefined): string {
  switch (mode) {
    case "playwright":
      return "Chromium";
    case "mock":
      return "Simulator";
    case "auto":
      return "Chromium (strict auto)";
    default:
      return mode ?? "unknown";
  }
}

/** Human label for the decision engine behind a run. */
export function llmLabel(provider: string | undefined, model: string | undefined): string {
  if (!provider || provider === "none") return "Heuristic policies";
  return model && model !== "—" ? `${provider} · ${model}` : provider;
}

// ---------------------------------------------------------------------------
// Context — one poller for the whole app, readable from anywhere.
// ---------------------------------------------------------------------------
const FALLBACK: EngineState = {
  health: null,
  reachable: false,
  online: false,
  error: null,
  refresh: () => {},
};

const EngineContext = createContext<EngineState>(FALLBACK);

export function EngineProvider({ children }: { children: ReactNode }) {
  const engine = useEngine();
  return <EngineContext.Provider value={engine}>{children}</EngineContext.Provider>;
}

export function useEngineStatus(): EngineState {
  return useContext(EngineContext);
}
