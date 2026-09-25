import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Dashboard from "./Dashboard";
import { EngineProvider } from "../hooks/useEngine";
import type { Health, Inspection } from "../types";

const apiMock = vi.hoisted(() => ({
  inspections: vi.fn(),
  health: vi.fn(),
}));

vi.mock("../lib/api", () => ({ api: apiMock }));

const HEALTH: Health = {
  status: "ok",
  app: "PROBE",
  llm_provider: "none",
  llm_model: "—",
  browser_mode: "mock",
  active_inspections: 0,
};

/** Factory for an inspection row; pass only the fields a test cares about. */
function inspection(overrides: Partial<Inspection>): Inspection {
  return {
    id: "insp_1",
    url: "http://127.0.0.1:5174/",
    depth: "quick",
    focus: ["chaos", "user"],
    goals: [],
    status: "completed",
    error: null,
    created_at: "2026-09-25T09:35:45.869+00:00",
    started_at: null,
    finished_at: null,
    duration_s: 5.4,
    report: null,
    finding_count: 0,
    agent_count: 0,
    ...overrides,
  };
}

function renderDashboard() {
  return render(
    <MemoryRouter>
      <EngineProvider>
        <Dashboard />
      </EngineProvider>
    </MemoryRouter>,
  );
}

describe("Dashboard", () => {
  beforeEach(() => {
    apiMock.inspections.mockReset();
    apiMock.health.mockReset().mockResolvedValue(HEALTH);
  });

  it("counts agent runs from the data instead of a hard-coded 5", async () => {
    apiMock.inspections.mockResolvedValue([
      inspection({ id: "insp_1", agent_count: 2, finding_count: 1 }),
      inspection({ id: "insp_2", url: "https://example.com", agent_count: 6 }),
    ]);

    renderDashboard();

    // "2 total" is the one place the row count renders as a single text node.
    await waitFor(() => expect(screen.getByText("2 total")).toBeDefined());

    // 2 + 6 = 8, deliberately not the 5 the dashboard used to hard-code.
    const agentRuns = screen.getByText("Agent runs").parentElement!;
    expect(agentRuns.textContent).toContain("8");
    expect(agentRuns.textContent).toContain("Technical · UX · Chaos · User · Review");
  });

  it("reports a different total when the data changes", async () => {
    apiMock.inspections.mockResolvedValue([
      inspection({ id: "insp_1", agent_count: 4 }),
      inspection({ id: "insp_2", agent_count: 4 }),
      inspection({ id: "insp_3", agent_count: 1 }),
    ]);

    renderDashboard();

    await waitFor(() => expect(screen.getByText("3 total")).toBeDefined());
    const agentRuns = screen.getByText("Agent runs").parentElement!;
    expect(agentRuns.textContent).toContain("9");
  });

  it("totals findings and counts apps that surfaced issues", async () => {
    apiMock.inspections.mockResolvedValue([
      inspection({ id: "insp_1", agent_count: 4, finding_count: 2 }),
      inspection({ id: "insp_2", agent_count: 4, finding_count: 0 }),
      inspection({ id: "insp_3", agent_count: 4, finding_count: 3 }),
    ]);

    renderDashboard();

    await waitFor(() => expect(screen.getByText("5")).toBeDefined());
    const withFindings = screen.getByText("Apps with findings").parentElement!;
    expect(withFindings.textContent).toContain("2");
    expect(withFindings.textContent).toContain("of 3 inspected");
  });

  it("surfaces which engine the backend is actually running on", async () => {
    apiMock.inspections.mockResolvedValue([]);
    renderDashboard();

    await waitFor(() => expect(screen.getAllByText("Simulator").length).toBeGreaterThan(0));
    expect(screen.getAllByText("Heuristic policies").length).toBeGreaterThan(0);
  });

  it("offers a way in when nothing has been inspected yet", async () => {
    apiMock.inspections.mockResolvedValue([]);
    renderDashboard();

    await waitFor(() => expect(screen.getByText("No inspections yet")).toBeDefined());
    expect(screen.getByText("Start your first inspection")).toBeDefined();
  });

  it("tells the user how to start the backend when it is unreachable", async () => {
    apiMock.inspections.mockRejectedValue(new Error("500 Internal Server Error"));
    apiMock.health.mockRejectedValue(new Error("failed to fetch"));
    renderDashboard();

    await waitFor(() =>
      expect(screen.getByText("Cannot reach the PROBE backend")).toBeDefined(),
    );
    expect(screen.getByText(/uv run uvicorn app.main:app/)).toBeDefined();
  });
});
