import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

// Self-hosted variable fonts. These must be imported before index.css so the
// `--font-sans` / `--font-mono` tokens below actually resolve to a real face
// instead of silently falling back to system-ui.
import "@fontsource-variable/inter";
import "@fontsource-variable/jetbrains-mono";

import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
