import React, { useState } from "react";
import Dashboard from "./components/Dashboard.jsx";
import Documents from "./components/Documents.jsx";
import Chat from "./components/Chat.jsx";
import PromptRegistry from "./components/PromptRegistry.jsx";
import SecurityCenter from "./components/SecurityCenter.jsx";
import Observability from "./components/Observability.jsx";
import EvaluationView from "./components/EvaluationView.jsx";

const TABS = [
  { key: "dashboard", label: "Dashboard", Component: Dashboard },
  { key: "chat", label: "Chat", Component: Chat },
  { key: "documents", label: "Documents", Component: Documents },
  { key: "evaluation", label: "Evaluation", Component: EvaluationView },
  { key: "observability", label: "Observability", Component: Observability },
  { key: "security", label: "Security Center", Component: SecurityCenter },
  { key: "prompts", label: "Prompt Registry", Component: PromptRegistry },
];

export default function App() {
  const [active, setActive] = useState("dashboard");
  const ActiveComponent = TABS.find((t) => t.key === active)?.Component || Dashboard;

  return (
    <div className="app-shell">
      <div className="sidebar">
        <div className="brand">
          Enterprise AI Copilot
          <small>Fulcrum Digital — Month 3 Capstone</small>
        </div>
        {TABS.map((tab) => (
          <button
            key={tab.key}
            className={`nav-item ${active === tab.key ? "active" : ""}`}
            onClick={() => setActive(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="main">
        <ActiveComponent />
      </div>
    </div>
  );
}
