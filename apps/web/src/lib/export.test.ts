import { describe, expect, it } from "vitest";

import { reportToMarkdown } from "./export";
import type { ReportResponse } from "../types";

const REPORT: ReportResponse = {
  application: "127.0.0.1:5174",
  url: "http://127.0.0.1:5174/",
  inspection: "quick",
  duration: "0m 05s",
  duration_s: 5.39,
  agents: [
    {
      role: "chaos",
      label: "Chaos AI",
      goal: "Deliberately try to break the application.",
      discoveries: 2,
    },
  ],
  agent_count: 4,
  findings: 2,
  critical: 0,
  high: 1,
  medium: 1,
  low: 0,
  info: 0,
  by_category: { reliability: 1, ux: 1 },
  groups: {},
  top_findings: [],
  correlated: 1,
  browser: "simulator",
  generated_at: "2026-09-25T09:35:51.261+00:00",
  summary: "2 finding(s) validated (0 critical, 1 high, 1 medium, 0 low, 0 info).",
  items: [
    {
      id: "find_1",
      inspection_id: "insp_1",
      title: "Repeated action triggers duplicate requests",
      category: "reliability",
      classification: "confirmed_defect",
      severity: "high",
      confidence: 0.89,
      description: "Two clicks produced two charges.",
      expected: "The control should be guarded while a request is in flight.",
      actual: "Every click submits.",
      steps: ["click e6", "click e6"],
      recommendation: "Disable the control and send an idempotency key.",
      agents: ["chaos", "user"],
      reproduced: "3 / 3",
      url: "http://127.0.0.1:5174/#/checkout",
      correlated: true,
      created_at: "2026-09-25T09:35:51.249+00:00",
    },
  ],
};

describe("reportToMarkdown", () => {
  const markdown = reportToMarkdown(REPORT);

  it("opens with the application and its metadata", () => {
    expect(markdown.startsWith("# PROBE inspection — 127.0.0.1:5174")).toBe(true);
    expect(markdown).toContain("- **URL:** http://127.0.0.1:5174/");
    expect(markdown).toContain("- **Browser engine:** simulator");
  });

  it("renders the severity table with the real counts", () => {
    expect(markdown).toContain("| Critical | High | Medium | Low | Info |");
    expect(markdown).toContain("| 0 | 1 | 1 | 0 | 0 |");
  });

  it("includes the Review AI summary", () => {
    expect(markdown).toContain("2 finding(s) validated");
  });

  it("notes correlation when the Review AI merged findings", () => {
    expect(markdown).toContain("1 finding was correlated");
  });

  it("emits each finding with steps, expectation and recommendation", () => {
    expect(markdown).toContain("### 1. Repeated action triggers duplicate requests");
    expect(markdown).toContain("**High** · Confirmed defect · reliability · confidence 89%");
    expect(markdown).toContain("reproduced 3 / 3");
    expect(markdown).toContain("- **Expected:** The control should be guarded");
    expect(markdown).toContain("1. `click e6`");
    expect(markdown).toContain(
      "**Recommendation:** Disable the control and send an idempotency key.",
    );
  });

  it("names the agents that contributed", () => {
    expect(markdown).toContain("- **Found by:** Chaos AI, User Behavior AI");
  });

  it("renders the agent table", () => {
    expect(markdown).toContain("| Chaos AI | 2 | Deliberately try to break the application. |");
  });
});

describe("reportToMarkdown with no findings", () => {
  it("says so instead of leaving an empty section", () => {
    const markdown = reportToMarkdown({
      ...REPORT,
      findings: 0,
      high: 0,
      medium: 0,
      correlated: 0,
      summary: null,
      items: [],
    });
    expect(markdown).toContain("found nothing they could evidence");
    expect(markdown).toContain("No summary available.");
    expect(markdown).not.toContain("correlated across multiple agent");
  });
});
