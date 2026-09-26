import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import NewInspection from "./NewInspection";
import { EngineProvider } from "../hooks/useEngine";
import type { Health } from "../types";

const apiMock = vi.hoisted(() => ({
  createInspection: vi.fn(),
  health: vi.fn(),
}));

vi.mock("../lib/api", () => ({ api: apiMock }));

const HEALTH: Health = {
  status: "ok",
  app: "PROBE",
  llm_provider: "openai-compatible",
  llm_model: "test-model",
  allow_heuristic_mode: false,
  browser_mode: "playwright",
  active_inspections: 0,
};

function renderForm() {
  return render(
    <MemoryRouter>
      <EngineProvider>
        <NewInspection />
      </EngineProvider>
    </MemoryRouter>,
  );
}

describe("NewInspection", () => {
  beforeEach(() => {
    apiMock.createInspection.mockReset().mockResolvedValue({ id: "insp_new" });
    apiMock.health.mockReset().mockResolvedValue(HEALTH);
  });

  it("starts with a blank URL so a demo target is never silently inspected by default", () => {
    renderForm();
    const input = screen.getByLabelText("Website URL") as HTMLInputElement;
    expect(input.value).toBe("");
    expect(screen.getByRole("button", { name: "Start inspection" })).toBeDisabled();
  });

  it("requires explicit site authorization before starting", async () => {
    const user = userEvent.setup();
    renderForm();
    await user.type(screen.getByLabelText("Website URL"), "example.com");
    expect(screen.getByRole("button", { name: "Start inspection" })).toBeDisabled();
    await user.click(screen.getByLabelText(/I own this website or have explicit permission/));
    expect(screen.getByRole("button", { name: "Start inspection" })).toBeEnabled();
  });

  it("blocks live inspection when no LLM is configured unless offline mode is explicitly enabled", async () => {
    apiMock.health.mockResolvedValue({
      ...HEALTH,
      llm_provider: "none",
      llm_model: "—",
      allow_heuristic_mode: false,
    });
    const user = userEvent.setup();
    renderForm();

    await user.type(screen.getByLabelText("Website URL"), "example.com");
    await user.click(screen.getByLabelText(/I own this website or have explicit permission/));

    expect(await screen.findByText(/Live inspections are disabled until you set/)).toBeDefined();
    expect(screen.getByRole("button", { name: "Start inspection" })).toBeDisabled();
  });

  it("rejects an unusable URL and says why", async () => {
    const user = userEvent.setup();
    renderForm();

    const input = screen.getByLabelText("Website URL");
    await user.clear(input);
    await user.type(input, "not a url at all");
    await user.tab(); // blur

    expect(await screen.findByText("That is not a valid URL.")).toBeDefined();
    expect(screen.getByRole("button", { name: "Start inspection" })).toBeDisabled();
  });

  it("adds a scheme to a bare host instead of rejecting it", async () => {
    const user = userEvent.setup();
    renderForm();

    const input = screen.getByLabelText("Website URL");
    await user.clear(input);
    await user.type(input, "example.com");
    await user.tab();

    expect(screen.queryByText("That is not a valid URL.")).toBeNull();
    expect(screen.getByRole("button", { name: "Start inspection" })).toBeDisabled();
    await user.click(screen.getByLabelText(/I own this website or have explicit permission/));

    await user.click(screen.getByRole("button", { name: "Start inspection" }));
    await waitFor(() => expect(apiMock.createInspection).toHaveBeenCalled());
    expect(apiMock.createInspection.mock.calls[0][0].url).toBe("https://example.com");
  });

  it("sends the chosen depth and focus with the request", async () => {
    const user = userEvent.setup();
    renderForm();

    await user.click(screen.getByLabelText(/Deep/));
    await user.click(screen.getByLabelText(/Chaos/)); // untick one of the four
    await user.click(screen.getByLabelText("Website URL"));
    await user.type(screen.getByLabelText("Website URL"), "example.com");
    await user.click(screen.getByLabelText(/I own this website or have explicit permission/));

    await user.click(screen.getByRole("button", { name: "Start inspection" }));

    await waitFor(() => expect(apiMock.createInspection).toHaveBeenCalled());
    const payload = apiMock.createInspection.mock.calls[0][0];
    expect(payload.depth).toBe("deep");
    expect(payload.focus).toEqual(["technical", "ux", "user"]);
  });

  it("shows a backend error rather than failing silently", async () => {
    apiMock.createInspection.mockRejectedValue(new Error("422 bad url"));
    const user = userEvent.setup();
    renderForm();

    await user.type(screen.getByLabelText("Website URL"), "example.com");
    await user.click(screen.getByLabelText(/I own this website or have explicit permission/));
    await user.click(screen.getByRole("button", { name: "Start inspection" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("422 bad url");
  });
});
