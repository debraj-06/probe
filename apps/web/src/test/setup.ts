import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
});

// jsdom implements neither of these; components use both.
if (!("scrollTo" in Element.prototype)) {
  // @ts-expect-error -- jsdom gap
  Element.prototype.scrollTo = () => {};
}

if (!window.URL.createObjectURL) {
  window.URL.createObjectURL = vi.fn(() => "blob:mock");
  window.URL.revokeObjectURL = vi.fn();
}
