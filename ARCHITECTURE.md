# PROBE architecture

How the pieces fit together, and the decisions behind them.

---

## 1. Shape of the system

```
                    ┌──────────────────────────────────────────┐
   HTTP / WS        │              FastAPI (app/)               │
 ┌──────────┐  ──── ▶│  routes.py ──┬── orchestrator.py         │
 │ browser  │        │              │        │                  │
 └──────────┘        │              │        ├── BrowserPool    │
                     │              │        ├── agents/        │
                     │              │        └── evidence.py    │
                     │  ws.py ── events.py (EventBus)           │
                     │  db.py (sqlite3)                         │
                     └──────────────────────────────────────────┘
```

The frontend never talks to the database. It talks REST for snapshots and a
WebSocket for the live feed, and both are backed by the same `EventBus`, so a
reconnecting client sees exactly the same stream.

---

## 2. The agent loop

One loop, five agents. `Agent.run()` in `app/agents/base.py`:

```
observe ──▶ decide ──▶ execute ──▶ detect_anomalies ──▶ investigate ──▶ commit
   ▲          │                          │                   │            │
   │          │ policy or LLM            │ heuristics        │ replay     │ finding
   │          ▼                          ▼                   ▼            ▼
 Observation  Decision                list[str]         Investigation   Discovery
 (elements,   (action + args          symptoms           reproductions   title,
  url, text,  + thought)                                + evidence      severity,
  console,                                             steps, ...
  network,
  flags)
```

### `decide` — policy or model

`Decision.source` records which one fired. With `PROBE_LLM_PROVIDER=none` the
`app/agents/policy.py` classes run:

| Policy | Bias |
|---|---|
| `TechnicalPolicy` | inputs before controls — fill a form, then submit it |
| `UXPolicy` | reads labels and affordances, prefers the primary control |
| `ChaosPolicy` | hostile input, repeated clicks, reload/back abuse, longer disruption cadence |
| `UserPolicy` | chases a goal: search field → Enter → search button → product links → add to cart → cart → checkout → pay |

Policies share bookkeeping through `Policy`: `clicked`, `typed`, `visited`,
`field_attempts`, `awaiting_enter`, and a value-independent `_key(element)`.

> **Why `_key()` exists.** Element ids are re-assigned on every render, so
> "have I clicked this?" can never be answered with an id. `_key()` is
> `tag + label + type`, which is stable. It deliberately **excludes the current
> value** of an input — a value-dependent key made the search field look
> perpetually untyped.

### `detect_anomalies` — heuristics over two observations

Compares the observation before and after an action and the `ActionResult`, and
returns symptom strings. `ANOMALY_RULES` then maps symptoms to a finding
template by regex precedence:

```
duplicate request → search error → cart lost on back → layout overflow →
console error → no feedback → slow → failed request → element not found
```

Order matters. A generic "console error appeared" rule placed above the
structural rules mislabels long-input overflow, so structural flags are
evaluated first.

Two rules are deliberately narrow:

- **"no visible response"** requires a form control **and** zero new network
  requests. In a hash-routed SPA nearly every click leaves the DOM signature
  unchanged, so the broad version fires constantly.
- **"action failed"** is skipped when `error_kind == "harness"`.

### `investigate` — replay until it reproduces

Re-navigates to the URL and replays the last four recorded actions
`PROBE_REPRODUCE_ATTEMPTS` times, counting recurrences. Reproduction strength is
expressed through **confidence**, not severity:

```python
confidence = min(0.95, 0.5 + 0.13 * reproductions
                      + (0.08 if console evidence else 0))
if reproductions == 0: confidence = min(confidence, 0.55)
```

Severity comes from the *type* of defect only. A reproducible-but-low-impact
issue is a high-confidence medium, not an inflated high.

### `commit` — dedupe, then hand to Review

`Agent` keeps a per-agent title set so one agent cannot file the same finding
twice. Discoveries go to `ReviewAgent`.

---

## 3. The Review AI

`app/agents/review.py`. Runs once, after every explorer finishes.

```
discoveries ──▶ dedupe ──▶ correlate ──▶ classify ──▶ (optional) LLM summary
                                                              │
                                                   contributing_factors
                                                   merged recommendations
                                                   merged description
```

**Correlation** merges findings that share a URL *and* an identical control
target, or that have overlapping tags. A merged finding records every
contributing agent in `agents[]` and every observation in
`source.contributing_factors`, e.g.

```
Interaction produces no visible feedback (observed by user)
```

**Classification** is rule-based: `ux_issue` for ux/ui/accessibility,
`confirmed_defect` for high/critical severity or strong console/network
evidence plus a reproduction, `improvement` otherwise. With an LLM configured,
the model writes the prose summary — the grouping stays deterministic.

---

## 4. Browser layer

```python
class BrowserController(ABC):
    async def start() / close()
    async def navigate(url) / go_back() / reload()
    async def click(target) / type_text(target, text)
    async def scroll(direction, amount) / press_key(key) / wait(seconds)
    async def observe() -> Observation          # elements, url, text, console, network, flags
    async def get_state() -> dict
    async def get_dom() -> str
    async def screenshot(path) -> Path | None
```

Two implementations behind that one interface:

- **`PlaywrightController`** — real Chromium, records console messages and
  network responses, attaches `data-probe-id` to every visible element.
- **`MockBrowser`** — a hash-routed simulator of the demo shop with the same
  six planted defects. Used when Chromium is unavailable, and by the tests.

`BrowserPool.create()` implements `browser_mode`:

```
auto ──────▶ try Playwright ──ok──▶ use it
                 │
                 └──fail──▶ MockBrowser (fell_back = true, surfaced in the report)
playwright ─▶ Playwright, hard error if it cannot launch
mock ──────▶ MockBrowser
```

### Element identity

`COLLECT_ELEMENTS_JS` assigns ids `e1..eN` in a **deterministic order** — sorted
by an identity string of `tag | aria/placeholder/name | href | type | role`. The
current value of an input is deliberately excluded, so typing does not reshuffle
every id on the page. Ids are also written to the DOM as `data-probe-id`, so a
locator stays valid across a re-render.

### `ActionResult`

```python
ok: bool
action: str
target: Any
detail: str
error: str | None
error_kind: str      # "app" | "harness"
duration_ms: float
element_tag: str
element_label: str
before: dict
after: dict
```

`error_kind` exists because "the browser could not do this" and "the
application broke" are different things. `go_back` with no history raises
`_HarnessError` inside `PlaywrightController._run`, which is recorded but never
becomes a finding.

---

## 5. Evidence

`EvidenceStore` writes to `data/inspections/{inspection_id}/{screens,data}/`
and indexes each artefact in SQLite so it can be served at
`/evidence/inspections/{id}/...` and attached to a finding later.

Evidence kinds: `screenshot`, `console`, `network`, `state`, `dom`, `video`.
`save_screenshot()` and `save_json()` return an `EvidenceRef` that the agent
threads into its `Discovery`, so the screenshot taken *during* an investigation
ends up on the finding that needed it.

---

## 6. Storage

Plain `sqlite3` from the standard library, one connection guarded by an
`RLock` (`check_same_thread=False`) because agents run in threads via
`asyncio.to_thread`. No ORM, no migrations — `SCHEMA` is created on open.

Tables: `inspections`, `agent_runs`, `events`, `findings`, `evidence`.

`events` is the spine of the product: `EventBus.emit()` writes the row and fans
it out to every subscriber queue for that inspection. `ws.py` replays
`history()` and then streams, so a client that connects mid-run is never lost.

Cancellation uses a `threading.Event` rather than an `asyncio.Event` so that
`POST /inspections/{id}/stop` — a sync route — can signal the loop.

---

## 7. The report

`Orchestrator._build_report()` assembles:

```
application, url, inspection, duration, duration_s
agents[], agent_count
findings, critical, high, medium, low, info
by_category, groups
top_findings          # ordered digest — id, title, severity, category,
                      #   classification, confidence, correlated, agents
correlated, browser, generated_at
```

`top_findings` exists because the dashboard needs a short ordered list, not the
full finding objects; the frontend's `ReportFindingSummary` maps onto it
directly.

---

## 8. Frontend

Vite + React 18 + TypeScript + Tailwind v4, hash-routed:

```
/                Dashboard — recent inspections + latest findings
/new             New inspection form
/i/:id           InspectionWorkspace
                 ├── AgentsPanel      live status per agent
                 ├── LivePreview      newest screenshot
                 ├── ActivityFeed     folded event stream
                 ├── FindingsFeed     list + FindingDetail
                 └── FinalReport      severity counts, top findings, download
```

`useInspectionStream` opens the WebSocket and **also** polls REST every 4s, so
the workspace keeps working if the socket drops. Events are folded into agent,
screenshot, finding and activity state.

The Vite dev server proxies `/api`, `/evidence` and `/ws` to the backend, so the
browser never needs to know where the API lives — which is what makes the
sandboxed preview work.

---

## 9. LLM abstraction

```python
class LLMClient(ABC):
    async def decide(self, *, system: str, messages: list[dict],
                     tools: list[dict]) -> LLMResponse: ...
    async def complete(self, *, system: str, messages: list[dict]) -> str: ...
```

`decide()` is a **forced tool call** against `agent_tool_definition()` — the
`probe_action` tool whose JSON schema is the whole action surface. Anything with
function calling is therefore a drop-in.

`create_llm(settings)` resolves `PROBE_LLM_PROVIDER`:

| Value | Implementation |
|---|---|
| `none` | `None` → policies take over |
| `openai` | `OpenAICompatibleClient` |
| `openai-compatible` | `OpenAICompatibleClient` + `PROBE_LLM_BASE_URL` |
| `anthropic` | `AnthropicClient` |
| `gemini` | `GeminiClient` |

`normalize_action()` maps model-produced aliases (`tap`, `fill`, `goto`,
`back`, …) onto canonical action names, so a provider that prefers different
vocabulary still works.

---

## 10. Running real Chromium

`playwright install chromium` downloads the browser but **not** the shared
libraries it links against. On a slim Debian/Ubuntu image you also need:

```bash
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  libnss3 libnspr4 libasound2t64 libatk1.0-0t64 libatk-bridge2.0-0t64 \
  libatspi2.0-0t64 libxkbcommon0 libxdamage1 libcups2t64 libdrm2 libgbm1 \
  libpango-1.0-0 libcairo2 libxcomposite1 libxfixes3 libxrandr2 \
  libx11-6 libxcb1 libxext6 fonts-liberation
```

Verify with `ldd ~/.cache/ms-playwright/chromium*/chrome-linux/chrome | grep "not found"`
— it must print nothing. PROBE is launched with `--no-sandbox`, so it works as
an unprivileged user.

If any of this is missing, `browser_mode=auto` falls back to the simulator
rather than failing the inspection.

---

## 11. Tests

`services/api/tests/` — 26 tests, `uv run pytest` from `services/api`.

| File | Covers |
|---|---|
| `test_api.py` | health, create/run, URL normalisation, 422s, events, findings, report, stop, 404s, WebSocket |
| `test_agents.py` | simulator defects, anomaly detection, every policy, Review dedupe/correlate, LLM schema helpers, a full orchestrator run |

`conftest.py` builds a `Settings` fixture with `browser_mode="mock"`,
`llm_provider="none"` and a tmp data dir, and exposes `wait_for_finish()` which
polls until the inspection leaves `running`. `pythonpath = ["."]` in
`pyproject.toml` is what lets the tests import `app` without an install step.

Run with the simulator so the suite is deterministic and needs no browser.
