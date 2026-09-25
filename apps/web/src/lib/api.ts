/** Tiny fetch wrapper around the PROBE API. */

import type {
  Evidence,
  FindingDetail,
  Health,
  Inspection,
  InspectionCreate,
  InspectionDetail,
  ProbeEvent,
  ReportResponse,
} from "../types";

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    let detail = "";
    try {
      detail = await response.text();
    } catch {
      /* ignore */
    }
    throw new Error(`${response.status} ${response.statusText} ${detail}`.trim());
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<Health>("/api/health"),

  inspections: () => request<Inspection[]>("/api/inspections"),

  inspection: (id: string) => request<InspectionDetail>(`/api/inspections/${id}`),

  createInspection: (payload: InspectionCreate) =>
    request<Inspection>("/api/inspections", {
      method: "POST",
      body: JSON.stringify({ autostart: true, ...payload }),
    }),

  stopInspection: (id: string) =>
    request<{ id: string; stopping: boolean }>(`/api/inspections/${id}/stop`, {
      method: "POST",
    }),

  /** Re-run an inspection with exactly the settings it was created with. */
  restartInspection: (id: string) =>
    request<{ id: string; restarted: boolean }>(`/api/inspections/${id}/restart`, {
      method: "POST",
    }),

  events: (id: string) => request<ProbeEvent[]>(`/api/inspections/${id}/events`),

  /** Every screenshot / console / network artifact captured for an inspection. */
  evidence: (id: string) => request<Evidence[]>(`/api/inspections/${id}/evidence`),

  finding: (id: string) => request<FindingDetail>(`/api/findings/${id}`),

  report: (id: string) => request<ReportResponse>(`/api/inspections/${id}/report`),
};

/** Public URL for an evidence file served by the backend. */
export function evidenceUrl(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  return `${BASE}${url}`;
}

/** WebSocket URL for the live event stream of one inspection. */
export function streamUrl(inspectionId: string): string {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.host}/ws/inspections/${inspectionId}`;
}
