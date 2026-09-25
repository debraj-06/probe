# PROBE

**Autonomous AI-powered web application testing & investigation platform.**

You give PROBE a URL. A team of specialised agents opens it in a real browser,
explores it, notices behaviour that looks wrong, investigates it until it can
reproduce it, and hands you a report with screenshots and console/network
evidence attached — before you ever had to click anything yourself.

```
 ┌──────────────┐   POST /api/inspections   ┌───────────────────────────┐
 │  Dashboard   │ ────────────────────────▶ │      Orchestrator         │
 │  React + TS  │ ◀──── WebSocket stream ── │  ┌─────────────────────┐  │
 └──────────────┘   ws/inspections/{id}     │  │ Technical  UX/UI    │  │
                                            │  │ Chaos      User      │  │
 ┌──────────────┐                           │  └──────────┬──────────┘  │
 │   DemoShop   │ ◀──── Playwright ──────── │             ▼             │
 │  (target app)│                           │  │   Review AI (merge)  │  │
 └──────────────┘                           │  └─────────────────────┘  │
                                            └───────────────────────────┘
```

---

## Quick start

```bash
# 1. dependencies (one time)
pnpm install
pnpm --filter @probe/api install:py        # uv sync
uv run --project services/api playwright install chromium   # optional, real browser

# 2. everything at once
./scripts/dev.sh
```

Then open **http://127.0.0.1:5173**, paste `http://demoshop.local:5174/` (or
`http://127.0.0.1:5174/`), pick a depth and hit **Start inspection**.

No Chromium? PROBE runs `browser_mode=auto`, which tries Playwright and quietly
falls back to a built-in simulator of the demo shop, so the whole platform is
demonstrable offline.

### Run the pieces by hand

```bash
# frontend
pnpm run dev

# backend
cd services/api && uv run uvicorn app.main:app --port 8000

# the app PROBE inspects
pnpm run dev:demo
```

### Test

```bash
pnpm test                      # 26 backend + 34 frontend tests
pnpm test:api                  # backend only   (pytest)
pnpm test:web                  # frontend only  (vitest + Testing Library)
pnpm typecheck                 # tsc across the dashboard
cd services/api && uv run ruff check app
```

The frontend suite renders the real components against a mocked API client. It
includes regression tests for three defects that shipped in the dashboard: a
hard-coded agent count, a pre-filled inspection URL that could not resolve, and
a backend `restart` endpoint nothing in the UI ever called.

---

## The agents

| Agent | What it is looking for |
|---|---|
| **Technical** | Failing requests, console errors, unlabelled or unreachable controls, layout overflow from long input |
| **UX / UI** | Missing feedback, dead controls, confusing affordances, actions that do nothing visible |
| **Chaos** | Deliberately breaks things: repeated clicks, hostile input, back-button and reload abuse |
| **User Behavior** | Behaves like a real person with a real goal — search, add to cart, fill checkout, pay |
| **Review** | Not an explorer. Reads everyone's discoveries, merges the ones describing the same defect, and writes the final report |

Every agent runs the **same loop**:

```
observe → decide → execute → detect anomalies → investigate (reproduce) → commit
```

Policies drive that loop when no LLM is configured. Set `PROBE_LLM_PROVIDER`
and the same loop is driven by a model instead — the agents, the tools and the
evidence pipeline are unchanged.

---

## The demo

`demoshop/` is a small shop with **six deliberately planted defects**, so an
inspection always has something real to find:

| # | Defect | Severity |
|---|---|---|
| 1 | Repeated clicks on *Pay now* submit duplicate payments — no disabled state, no idempotency | high |
| 2 | Checkout gives zero feedback while the payment is in flight | medium |
| 3 | Searching for a term with no results crashes the results view, and *Dismiss* never restores it | high |
| 4 | The review textarea has no length or wrapping constraint and overflows the layout | medium |
| 5 | Browser **Back** away from the cart silently discards its contents | high |
| 6 | `?slow=1` makes payment take six seconds with no progress indicator | medium |

See [`demoshop/BUGS.md`](demoshop/BUGS.md) for where each one lives in the code.

---

## The Review AI — the part worth watching

This is the centrepiece. Four agents exploring independently will each stumble
over the same underlying defect from a different angle. The Review agent
correlates them:

```
chaos  ──┐
user   ──┼──▶  ONE finding
ux     ──┘     "Interaction produces no visible feedback"
               correlated across: chaos, user
               contributing factors:
                 • Interaction produces no visible feedback (observed by user)
```

A merged finding carries every contributing agent, the merged reproduction
count (`3 / 3`), the union of the screenshots and console evidence, and a single
set of recommendations. `GET /api/findings/{id}` returns it all as
`contributing_factors`.

Findings are merged when they share a URL **and** the same control target, or
when their tags overlap.

---

## The dashboard

Three screens, one live stream.

- **Dashboard** — every inspection, its severity distribution at a glance, and an
  engine strip that reports what the backend is really running on: browser
  engine (Chromium vs simulator) and decision engine (model vs heuristic
  policies). Both change what a result means, so neither is left implicit.
- **New inspection** — URL, depth, focus and optional goals. A bare host name is
  accepted and gets `https://` added; an unusable URL is rejected in place with
  a reason rather than failing after submit.
- **Inspection workspace** — agents on the left, the live browser capture in the
  middle framed as a browser window, the event stream on the right. Findings
  open a side panel with expected/actual, reproduction steps, the correlation
  reasoning, and the screenshot / console / network evidence.

Two things worth knowing:

- **Re-run.** A finished inspection can be re-run in place with its original
  settings (`↻ Re-run`) — this is the `POST /api/inspections/{id}/restart`
  endpoint, which the UI did not previously expose.
- **Export.** The final report downloads as **Markdown** (ready to paste into an
  issue) or **JSON**. Both are generated client-side from the report payload, so
  no extra endpoint is involved.

Typography is Inter and JetBrains Mono, self-hosted via `@fontsource-variable`
rather than a font CDN, so the dashboard renders identically offline.

---

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | liveness + effective config |
| `POST` | `/api/inspections` | start an inspection (`url`, `depth`, `focus`, `goals`) |
| `GET` | `/api/inspections` | recent inspections |
| `GET` | `/api/inspections/{id}` | one inspection + report |
| `POST` | `/api/inspections/{id}/stop` | cancel at the next safe point |
| `POST` | `/api/inspections/{id}/restart` | re-run with the same settings |
| `GET` | `/api/inspections/{id}/events` | full event log |
| `GET` | `/api/inspections/{id}/findings` | findings for an inspection |
| `GET` | `/api/inspections/{id}/report` | final report (incl. `top_findings`) |
| `GET` | `/api/inspections/{id}/screenshot/latest` | newest screenshot |
| `GET` | `/api/inspections/{id}/evidence` | all evidence for an inspection |
| `GET` | `/api/findings/{id}` | finding detail + `contributing_factors` |
| `WS` | `/ws/inspections/{id}` | live event stream (replays history, then streams) |
| `GET` | `/evidence/...` | screenshots and JSON evidence as static files |

Interactive docs at `http://127.0.0.1:8000/docs`.

### Depths

`quick` 8 steps · `balanced` 16 · `deep` 28 · `extreme` 45 — per agent.

### Event vocabulary

```
inspection.created|started|finished
agents.assigned
agent.started|thinking|action|suspicion|investigating|reproducing|
        reproduced|finding|error|finished
browser.navigated|screenshot
review.started|correlated|completed
finding.created
```

---

## Configuration

Everything is a `PROBE_`-prefixed env var — copy [`.env.example`](.env.example)
to `.env`. Nothing is required; the defaults run offline.

```bash
# LLM — provider-agnostic, see "Plugging in a provider" below
PROBE_LLM_PROVIDER=none            # none | openai | anthropic | gemini | openai-compatible
PROBE_LLM_MODEL=
PROBE_LLM_API_KEY=
PROBE_LLM_BASE_URL=                # only for openai-compatible

# Browser
PROBE_BROWSER_MODE=auto            # auto | playwright | mock
PROBE_HEADLESS=true
PROBE_RECORD_VIDEO=false

# Agents
PROBE_MAX_STEPS_PER_AGENT=20
PROBE_AGENT_STEP_DELAY=0.15
PROBE_SLOW_ACTION_MS=2500
PROBE_REPRODUCE_ATTEMPTS=3
PROBE_MOCK_LATENCY=1.2

# Server / storage
PROBE_HOST=0.0.0.0
PROBE_PORT=8000
PROBE_DATA_DIR=data
PROBE_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

---

## Plugging in a provider

The agent loop never talks to a vendor SDK. It talks to one interface:

```python
class LLMClient(ABC):
    async def decide(self, *, system: str, messages: list[dict], tools: list[dict]) -> LLMResponse: ...
    async def complete(self, *, system: str, messages: list[dict]) -> str: ...
```

`create_llm(settings)` in `app/llm/factory.py` picks an implementation from
`PROBE_LLM_PROVIDER` and returns `None` when it is `none`, which is what makes
the deterministic policies take over. Three implementations ship today:

- `OpenAICompatibleClient` — anything speaking the OpenAI chat-completions API
  (OpenAI itself, OpenRouter, vLLM, Ollama, LM Studio, …)
- `AnthropicClient` — the Messages API
- `GeminiClient` — `generateContent`

`decide()` is a **forced tool call**: the model must answer by calling the
`probe_action` tool whose schema is the entire action surface (`click`,
`type_text`, `scroll`, `navigate`, `go_back`, `reload`, `press_key`, `wait`,
`screenshot`, `get_dom`, `finish`). That means a provider only has to support
tool/function calling to be a drop-in.

To add a fourth provider, implement `LLMClient` and register it in
`create_llm()` — no agent, route or schema changes.

---

## Layout

```
probe/
├── apps/web/            React + TS + Tailwind dashboard (Vite, port 5173)
│   └── src/
│       ├── components/          Dashboard, NewInspection, InspectionWorkspace
│       │   └── workspace/       agents, live preview, activity, findings, report
│       ├── hooks/               useInspectionStream (WS + REST fallback),
│       │                        useEngine (live backend/browser/LLM status)
│       ├── lib/                 api client, formatters, report export (md/json)
│       ├── test/                vitest setup
│       └── types.ts             shared API types (mirrors the Pydantic schemas)
├── demoshop/            the target app — 6 planted defects (port 5174)
├── services/api/        FastAPI backend
│   ├── app/
│   │   ├── agents/      base loop, roles, policies, Review AI, tool schemas
│   │   ├── browser/     PlaywrightController + MockBrowser behind one ABC
│   │   ├── llm/         provider-agnostic client interface
│   │   ├── api/         REST routes
│   │   ├── orchestrator.py  runs agents concurrently, builds the report
│   │   ├── evidence.py      screenshots/JSON → disk + SQLite
│   │   ├── events.py        EventBus (persist + WebSocket fan-out)
│   │   ├── db.py            stdlib sqlite3 repositories
│   │   └── schemas.py       Pydantic models
│   └── tests/           26 tests
├── scripts/dev.sh       start API + dashboard + demo shop together
└── .env.example
```

Deeper design notes: [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## Known limitations

- **Element identity.** Ids are assigned deterministically from element
  identity (tag, aria/placeholder/name, href, type), so they survive
  re-renders and typing. A control that is genuinely removed from the DOM
  between observation and action still reads as "element not found".
- **Harness vs app failures.** An action the *browser* cannot perform (e.g.
  `go_back` with no history) is recorded with `error_kind="harness"` and never
  becomes a finding. Everything else is treated as app behaviour.
- **Correlation is lexical.** Findings merge on URL + control target or
  overlapping tags, not on semantic similarity. With an LLM configured, the
  Review agent's summary is model-written but the grouping is still rule-based.
- **Chromium needs system libraries.** On a slim Debian/Ubuntu image,
  `uv run playwright install chromium` alone is not enough — see
  [ARCHITECTURE.md](ARCHITECTURE.md#running-real-chromium).
- **Video recording** is opt-in (`PROBE_RECORD_VIDEO=true`) and is copied into
  the inspection's evidence folder when enabled.
- **One inspection at a time.** Each agent gets its own Chromium, so a balanced
  four-agent run is four browsers. That is fine on a laptop, but queue
  inspections rather than firing several at once — and use `quick` if the machine
  is small. `browser_mode=mock` has no such cost.
