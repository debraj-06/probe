import { describe, expect, it } from "vitest";

import { browserLabel, llmLabel } from "./useEngine";

describe("browserLabel", () => {
  it("names the engine a human would recognise", () => {
    expect(browserLabel("playwright")).toBe("Chromium");
    expect(browserLabel("mock")).toBe("Simulator");
    expect(browserLabel("auto")).toBe("Chromium (strict auto)");
  });

  it("survives a missing health response", () => {
    expect(browserLabel(undefined)).toBe("unknown");
  });
});

describe("llmLabel", () => {
  it("says heuristic policies when no provider is configured", () => {
    expect(llmLabel("none", "—")).toBe("Heuristic policies");
    expect(llmLabel(undefined, undefined)).toBe("Heuristic policies");
  });

  it("shows provider and model together", () => {
    expect(llmLabel("openai", "gpt-4o")).toBe("openai · gpt-4o");
  });

  it("falls back to the provider alone when the model is a placeholder", () => {
    expect(llmLabel("anthropic", "—")).toBe("anthropic");
    expect(llmLabel("anthropic", "")).toBe("anthropic");
  });
});
