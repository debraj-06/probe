import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import InspectionWorkspace from "./InspectionWorkspace";
import type { InspectionDetail, InspectionStatus } from "../types";

const apiMock = vi.hoisted(() => ({
  finding: vi.fn(),
  stopInspection: vi.fn(),
  restartInspection: vi.fn(),
  report: vi.fn(),
}));

const streamMock = vi.hoisted(() => ({
  status: "completed" as InspectionStatus,
  refresh: vi.fn(),
}));

vi.mock("../lib/api", () => ({ api: apiMock, evidenceUrl: (u: string) => u }));

vi.mock("../hooks/useInspectionStream", () => ({
  useInspectionStream: () => ({
    loading: false,
    inspection: {
      id: "insp_1",
      url: "http://127.0.0.1:5174/",
      depth: "quick",
      focus: ["chaos"],
      goals: [],
      authorized: true,
      allow_mutations: false,
      status: streamMock.status,
      error: null,
      created_at: "2026-09-25T09:35:45.869+00:00",
      started_at: null,
      finished_at: null,
      duration_s: 5.4,
      report: null,
      finding_count: 1,
      agent_count: 4,
      agents: [],
      findings: [
        {
          id: "find_1",
          inspection_id: "insp_1",
          title: "Repeated action triggers duplicate requests",
          category: "reliability",
          classification: "confirmed_defect",
          severity: "high",
          confidence: 0.89,
          description: "",
          expected: null,
          actual: null,
          steps: [],
          recommendation: null,
          agents: ["chaos"],
          reproduced: "3 / 3",
          url: null,
          correlated: false,
          created_at: "2026-09-25T09:35:51.249+00:00",
        },
      ],
      events: [],
    } satisfies InspectionDetail,
    events: [],
    agents: {},
    findings: {
      find_1: {
        id: "find_1",
        inspection_id: "insp_1",
        title: "Repeated action triggers duplicate requests",
        category: "reliability",
        classification: "confirmed_defect",
        severity: "high",
        confidence: 0.89,
        description: "",
        expected: null,
        actual: null,
        steps: [],
        recommendation: null,
        agents: ["chaos"],
        reproduced: "3 / 3",
        url: null,
        correlated: false,
        created_at: "2026-09-25T09:35:51.249+00:00",
      },
    },
    screenshot: null,
    status: streamMock.status,
    error: null,
    refresh: streamMock.refresh,
  }),
}));

function renderWorkspace() {
  return render(
    <MemoryRouter initialEntries={["/inspection/insp_1"]}>
      <Routes>
        <Route path="/inspection/:id" element={<InspectionWorkspace />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("InspectionWorkspace", () => {
  beforeEach(() => {
    streamMock.status = "completed";
    apiMock.restartInspection.mockReset().mockResolvedValue({ id: "insp_1", restarted: true });
    apiMock.stopInspection.mockReset().mockResolvedValue({ id: "insp_1", stopping: true });
    apiMock.report.mockReset().mockRejectedValue(new Error("no report"));
    streamMock.refresh.mockReset().mockResolvedValue(undefined);
  });

  it("shows the target, its status and the finding count", () => {
    renderWorkspace();
    expect(screen.getByText("127.0.0.1:5174")).toBeDefined();
    expect(screen.getByText("Completed")).toBeDefined();
  });

  /**
   * The backend has always exposed POST /api/inspections/{id}/restart; nothing
   * in the UI ever called it. A finished run must be re-runnable in place.
   */
  it("re-runs a finished inspection through the restart endpoint", async () => {
    const user = userEvent.setup();
    renderWorkspace();

    const rerun = screen.getByRole("button", { name: /Re-run/ });
    await user.click(rerun);

    await waitFor(() => expect(apiMock.restartInspection).toHaveBeenCalledWith("insp_1"));
    expect(streamMock.refresh).toHaveBeenCalled();
  });

  it("keeps the final report pinned and lets the user minimize and restore it", async () => {
    const user = userEvent.setup();
    renderWorkspace();

    await user.click(await screen.findByRole("button", { name: /Minimize/ }));
    expect(screen.getByText(/Final report · 1 finding/)).toBeDefined();

    await user.click(screen.getByRole("button", { name: "Expand report" }));
    expect(await screen.findByRole("button", { name: /Minimize/ })).toBeDefined();
  });

  it("offers Stop instead of Re-run while agents are working", () => {
    streamMock.status = "running";
    renderWorkspace();

    expect(screen.getByRole("button", { name: "Stop" })).toBeDefined();
    expect(screen.queryByRole("button", { name: /Re-run/ })).toBeNull();
  });

  it("stops a running inspection", async () => {
    streamMock.status = "running";
    const user = userEvent.setup();
    renderWorkspace();

    await user.click(screen.getByRole("button", { name: "Stop" }));

    await waitFor(() => expect(apiMock.stopInspection).toHaveBeenCalledWith("insp_1"));
  });

  it("surfaces a failed action instead of swallowing it", async () => {
    apiMock.restartInspection.mockRejectedValue(new Error("503 backend busy"));
    const user = userEvent.setup();
    renderWorkspace();

    await user.click(screen.getByRole("button", { name: /Re-run/ }));

    expect(await screen.findByText("503 backend busy")).toBeDefined();
  });
});
