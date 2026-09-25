import { NavLink, Route, Routes } from "react-router-dom";

import Dashboard from "./components/Dashboard";
import InspectionWorkspace from "./components/InspectionWorkspace";
import NewInspection from "./components/NewInspection";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/new", label: "New inspection", end: false },
];

export default function App() {
  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between border-b border-ink-700/70 bg-ink-950/70 px-5 py-3 backdrop-blur">
        <NavLink to="/" className="group flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-probe-500/40 bg-probe-500/10 font-mono text-sm font-bold text-probe-300 glow-text">
            P
          </span>
          <span>
            <span className="block text-sm font-semibold tracking-[0.2em] text-slate-100">
              PROBE
            </span>
            <span className="block text-[10px] tracking-wide text-slate-500">
              autonomous web investigation
            </span>
          </span>
        </NavLink>

        <nav className="flex items-center gap-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `rounded-lg px-3 py-1.5 text-sm transition ${
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
      </header>

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
