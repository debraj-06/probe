import { useCallback, useEffect, useRef, useState } from "react";

import { api, streamUrl } from "../lib/api";
import type {
  AgentRole,
  Finding,
  InspectionDetail,
  InspectionStatus,
  ProbeEvent,
  Severity,
} from "../types";

export interface AgentState {
  role: string;
  status: "idle" | "active" | "done" | "failed";
  lastMessage: string;
  steps: number;
  discoveries: number;
  lastAction: string;
}

export interface StreamState {
  loading: boolean;
  inspection: InspectionDetail | null;
  events: ProbeEvent[];
  agents: Record<string, AgentState>;
  findings: Record<string, Finding>;
  screenshot: { url: string; at: number } | null;
  status: InspectionStatus;
  error: string | null;
}

const EMPTY: StreamState = {
  loading: true,
  inspection: null,
  events: [],
  agents: {},
  findings: {},
  screenshot: null,
  status: "queued",
  error: null,
};

const MAX_EVENTS = 400;

function agentKey(role: string): string {
  return role;
}

function ensureAgent(agents: Record<string, AgentState>, role: string): AgentState {
  return (
    agents[agentKey(role)] ?? {
      role,
      status: "idle",
      lastMessage: "",
      steps: 0,
      discoveries: 0,
      lastAction: "",
    }
  );
}

/** Fold one live event into the workspace state. */
function applyEvent(state: StreamState, event: ProbeEvent): StreamState {
  const agents = { ...state.agents };
  const findings = { ...state.findings };
  let { status, screenshot, inspection } = state;

  const role = event.agent ?? "";
  const data = event.data ?? {};

  switch (event.type) {
    case "inspection.started":
    case "agents.assigned":
      status = "running";
      break;

    case "agent.started": {
      const agent = ensureAgent(agents, role);
      agents[role] = { ...agent, status: "active", lastMessage: event.message };
      break;
    }

    case "agent.action": {
      const agent = ensureAgent(agents, role);
      agents[role] = {
        ...agent,
        status: "active",
        lastMessage: event.message,
        lastAction: String(data.action ?? ""),
        steps: Number(data.step ?? agent.steps),
      };
      break;
    }

    case "agent.suspicion":
    case "agent.investigating":
    case "agent.reproducing":
    case "agent.reproduced":
    case "agent.thinking": {
      const agent = ensureAgent(agents, role);
      agents[role] = { ...agent, status: "active", lastMessage: event.message };
      break;
    }

    case "agent.finding": {
      const agent = ensureAgent(agents, role);
      agents[role] = {
        ...agent,
        discoveries: agent.discoveries + 1,
        lastMessage: event.message,
      };
      break;
    }

    case "agent.error": {
      const agent = ensureAgent(agents, role);
      agents[role] = { ...agent, status: "failed", lastMessage: event.message };
      break;
    }

    case "agent.finished": {
      const agent = ensureAgent(agents, role);
      const status = data.status === "failed" ? "failed" : "done";
      agents[role] = { ...agent, status, lastMessage: event.message };
      break;
    }

    case "browser.screenshot": {
      const url = String(data.url ?? "");
      if (url) screenshot = { url, at: Date.now() };
      break;
    }

    case "finding.created": {
      const id = String(data.finding_id ?? `pending-${event.id}`);
      findings[id] = {
        id,
        inspection_id: event.inspection_id,
        title: String(data.title ?? event.message),
        category: String(data.category ?? "functional"),
        classification: "confirmed_defect",
        severity: (data.severity as Severity) ?? "medium",
        confidence: Number(data.confidence ?? 0.5),
        description: "",
        expected: null,
        actual: null,
        steps: [],
        recommendation: null,
        agents: (data.agents as string[]) ?? (role ? [role] : []),
        reproduced: data.reproduced ? String(data.reproduced) : null,
        url: null,
        correlated: Boolean(data.correlated),
        created_at: event.ts,
      };
      break;
    }

    case "review.completed":
      status = inspection?.status === "failed" ? status : "running";
      break;

    case "inspection.finished":
      status = (data.status as InspectionStatus) ?? "completed";
      break;

    default:
      break;
  }

  return {
    ...state,
    agents,
    findings,
    status,
    screenshot,
    inspection,
    events: [event, ...state.events].slice(0, MAX_EVENTS),
  };
}

/** Merge a REST snapshot into the live state without losing live-only bits. */
function mergeDetail(state: StreamState, detail: InspectionDetail): StreamState {
  const findings = { ...state.findings };
  for (const finding of detail.findings) {
    findings[finding.id] = finding;
  }
  const agents = { ...state.agents };
  for (const run of detail.agents) {
    const existing = agents[run.role];
    agents[run.role] = {
      role: run.role as AgentRole,
      status:
        run.status === "completed"
          ? "done"
          : run.status === "failed"
            ? "failed"
            : run.status === "running"
              ? "active"
              : (existing?.status ?? "idle"),
      lastMessage: existing?.lastMessage || run.summary || "",
      steps: run.steps,
      discoveries: run.discoveries,
      lastAction: existing?.lastAction ?? "",
    };
  }
  return {
    ...state,
    loading: false,
    inspection: detail,
    agents,
    findings,
    status: detail.status,
    error: detail.error,
  };
}

export function useInspectionStream(inspectionId: string | undefined) {
  const [state, setState] = useState<StreamState>(EMPTY);
  const retryRef = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    if (!inspectionId) return;
    try {
      const detail = await api.inspection(inspectionId);
      setState((current) => mergeDetail(current, detail));
    } catch (error) {
      setState((current) => ({
        ...current,
        loading: false,
        error: error instanceof Error ? error.message : String(error),
      }));
    }
  }, [inspectionId]);

  useEffect(() => {
    if (!inspectionId) {
      setState(EMPTY);
      return;
    }

    let alive = true;
    const socketRef: { current: WebSocket | null } = { current: null };
    setState({ ...EMPTY });

    void refresh();

    const connect = () => {
      if (!alive) return;
      const socket = new WebSocket(streamUrl(inspectionId));
      socket.onmessage = (message) => {
        if (!alive) return;
        try {
          const event = JSON.parse(message.data as string) as ProbeEvent;
          setState((current) => applyEvent(current, event));
        } catch {
          /* ignore malformed frames */
        }
      };
      socket.onclose = () => {
        if (alive) retryRef.current = window.setTimeout(connect, 1500);
      };
      socketRef.current = socket;
    };

    connect();

    // poll while running so findings, evidence and the report stay fresh
    const poll = window.setInterval(() => {
      setState((current) => {
        if (current.status === "running" || current.loading) void refresh();
        return current;
      });
    }, 4000);

    return () => {
      alive = false;
      if (retryRef.current) window.clearTimeout(retryRef.current);
      window.clearInterval(poll);
      socketRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inspectionId]);

  return { ...state, refresh };
}
