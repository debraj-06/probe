import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import App from "./App";

const apiMock = vi.hoisted(() => ({
  health: vi.fn(),
  inspections: vi.fn(),
}));

vi.mock("./lib/api", () => ({ api: apiMock, evidenceUrl: (u: string) => u }));

// `BrowserRouter` lives in main.tsx, so App has to be given a router here.
function renderApp(route = "/") {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <App />
    </MemoryRouter>,
  );
}

const HEALTHY = {
  status: "ok",
  app: "PROBE",
  llm_provider: "none",
  llm_model: "—",
  browser_mode: "auto",
  active_inspections: 0,
};

describe("App shell", () => {
  it("shows a live engine readout once the backend answers", async () => {
    apiMock.health.mockResolvedValue({
      ...HEALTHY,
      llm_provider: "openai",
      llm_model: "gpt-4o",
      browser_mode: "playwright",
    });
    apiMock.inspections.mockResolvedValue([]);

    renderApp();

    // The header answers "is this a real browser and a real model?" — the two
    // facts that change how every result on screen should be read.
    await waitFor(() => expect(screen.getAllByText("Chromium").length).toBeGreaterThan(0));
    expect(screen.getAllByText("openai · gpt-4o").length).toBeGreaterThan(0);
    expect(screen.getByText("PROBE")).toBeDefined();
  });

  it("warns loudly when the backend is down", async () => {
    apiMock.health.mockRejectedValue(new Error("ECONNREFUSED"));
    apiMock.inspections.mockRejectedValue(new Error("ECONNREFUSED"));

    renderApp();

    await waitFor(() =>
      expect(screen.getAllByText(/Cannot reach the PROBE backend/).length).toBeGreaterThan(0),
    );
  });

  it("navigates between the dashboard and the new-inspection form", async () => {
    apiMock.health.mockResolvedValue(HEALTHY);
    apiMock.inspections.mockResolvedValue([]);
    const user = userEvent.setup();

    renderApp();

    await user.click(screen.getByRole("link", { name: "New inspection" }));
    expect(await screen.findByRole("heading", { name: "New inspection" })).toBeDefined();

    await user.click(screen.getByRole("link", { name: "Dashboard" }));
    expect(await screen.findByRole("heading", { name: "Inspections" })).toBeDefined();
  });

  it("handles an unknown route instead of rendering nothing", () => {
    apiMock.health.mockResolvedValue(HEALTHY);
    renderApp("/nope");

    expect(screen.getByText(/Nothing here/)).toBeDefined();
  });
});
