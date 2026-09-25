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
  llm_provider: "none",
  llm_model: "—",
  browser_mode: "mock",
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

  /**
   * Regression: the form used to pre-fill `https://demoshop.local` — HTTPS with
   * no port, which resolves to nothing, so the default "Start inspection" click
   * could never reach the demo shop it exists to demonstrate.
   */
  it("pre-fills a URL that actually reaches the demo shop", () => {
    renderForm();
    const input = screen.getByLabelText("Website URL") as HTMLInputElement;

    const parsed = new URL(input.value);
    expect(parsed.protocol).toBe("http:");
    expect(parsed.hostname).toBe("127.0.0.1");
    expect(parsed.port).toBe("5174");
  });

  it("starts with a valid form the user can submit immediately", () => {
    renderForm();
    expect(screen.getByRole("button", { name: "Start inspection" })).toBeEnabled();
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
    expect(screen.getByRole("button", { name: "Start inspection" })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Start inspection" }));
    await waitFor(() => expect(apiMock.createInspection).toHaveBeenCalled());
    expect(apiMock.createInspection.mock.calls[0][0].url).toBe("https://example.com");
  });

  it("sends the chosen depth and focus with the request", async () => {
    const user = userEvent.setup();
    renderForm();

    await user.click(screen.getByLabelText(/Deep/));
    await user.click(screen.getByLabelText(/Chaos/)); // untick one of the four

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

    await user.click(screen.getByRole("button", { name: "Start inspection" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("422 bad url");
  });
});
