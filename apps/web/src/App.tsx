import { NavLink, Route, Routes } from "react-router-dom";

import Dashboard from "./components/Dashboard";
import InspectionWorkspace from "./components/InspectionWorkspace";
import NewInspection from "./components/NewInspection";
import { EngineProvider, browserLabel, llmLabel, useEngineStatus } from "./hooks/useEngine";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/new", label: "New inspection", end: false },
];

/** PROBE mark — a radar sweep, matching the favicon. */
function LogoMark() {
  return (
    <span className="relative flex h-8 w-8 items-center justify-center rounded-lg border border-probe-500/40 bg-probe-500/10 glow-ring">
      <svg viewBox="0 0 32 32" className="h-5 w-5" aria-hidden>
        <circle cx="16" cy="16" r="11" fill="none" stroke="#22d3ee" strokeOpacity="0.3" strokeWidth="1.5" />
        <circle cx="16" cy="16" r="5.5" fill="none" stroke="#22d3ee" strokeOpacity="0.5" strokeWidth="1.5" />
        <circle cx="16" cy="16" r="2" fill="#67e8f9" />
        <path d="M16 16 L27 9.5" stroke="#67e8f9" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    </span>
  );
}

/**
 * Live engine readout. Answers the two questions the rest of the UI cannot:
 * is the backend actually reachable, and is this run driven by a real browser
 * and a model, or by the simulator and heuristic policies?
 */
function EngineStatus() {
  const { online, health, error } = useEngineStatus();

  const browser = browserLabel(health?.browser_mode);
  const llm = llmLabel(health?.llm_provider, health?.llm_model);

  return (
    <div
      className="hidden items-center gap-2 rounded-full border border-ink-700 bg-ink-900/70 py-1 pr-3 pl-2.5 md:flex"
      title={
        online
          ? `Backend online · browser: ${browser} · decisions: ${llm}`
          : (error ?? "Cannot reach the PROBE backend")
      }
    >
      <span className="relative flex h-2 w-2">
        {online ? (
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400/60" />
        ) : null}
        <span
          className={`relative inline-flex h-2 w-2 rounded-full ${
            online ? "bg-emerald-400" : "bg-rose-500"
          }`}
        />
      </span>
      <span className="font-mono text-[11px] text-slate-400">
        {online ? browser : "offline"}
      </span>
      <span className="h-3 w-px bg-ink-700" />
      <span className="max-w-[13rem] truncate font-mono text-[11px] text-slate-500">{llm}</span>
    </div>
  );
}

function Shell() {
  const { online } = useEngineStatus();

  return (
    <div className="flex h-full flex-col">
      <header className="z-20 flex flex-wrap items-center justify-between gap-3 border-b border-ink-700/70 bg-ink-950/80 px-4 py-2.5 backdrop-blur-md sm:px-5">
        <NavLink to="/" className="group flex items-center gap-2.5">
          <LogoMark />
          <span>
            <span className="block text-sm font-semibold tracking-[0.2em] text-slate-100">
              PROBE
            </span>
            <span className="block text-[10px] tracking-wide text-slate-500">
              autonomous web investigation
            </span>
          </span>
        </NavLink>

        <div className="flex items-center gap-3">
          <EngineStatus />
          <nav className="flex items-center gap-1 rounded-xl border border-ink-700/70 bg-ink-900/60 p-1">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1.5 text-sm transition-all duration-150 ${
                    isActive
                      ? "bg-ink-800 text-probe-300 shadow-[inset_0_0_0_1px_rgba(34,211,238,0.25)]"
                      : "text-slate-400 hover:bg-ink-850 hover:text-slate-200"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      {!online ? (
        <p className="border-b border-rose-500/25 bg-rose-500/10 px-5 py-1.5 text-center text-xs text-rose-300">
          Cannot reach the PROBE backend — start it with{" "}
          <code className="font-mono text-rose-200">
            cd services/api &amp;&amp; uv run uvicorn app.main:app --port 8000
          </code>
        </p>
      ) : null}

      <main className="min-h-0 flex-1 overflow-hidden">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/new" element={<NewInspection />} />
          <Route path="/inspection/:id" element={<InspectionWorkspace />} />
          <Route
            path="*"
            element={
              <div className="p-10 text-center text-slate-500">
                Nothing here.{" "}
                <NavLink to="/" className="text-probe-300 underline">
                  Back to dashboard
                </NavLink>
              </div>
            }
          />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <EngineProvider>
      <Shell />
    </EngineProvider>
  );
}
