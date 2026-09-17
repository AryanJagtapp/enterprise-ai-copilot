import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function SecurityCenter() {
  const [events, setEvents] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.securityEvents(100).then(setEvents).catch((e) => setError(e.message));
  }, []);

  const byType = events.reduce((acc, e) => {
    acc[e.event_type] = (acc[e.event_type] || 0) + 1;
    return acc;
  }, {});

  return (
    <div>
      <h1>Security Center</h1>
      <div className="subtitle">Real PII, prompt-injection, and policy-violation events recorded by the Security Gateway.</div>
      {error && <div className="error-banner">{error}</div>}

      <div className="grid">
        {Object.entries(byType).map(([type, count]) => (
          <div className="stat-tile" key={type}>
            <div className="value">{count}</div>
            <div className="label">{type.replace(/_/g, " ")}</div>
          </div>
        ))}
        {Object.keys(byType).length === 0 && <div className="stat-tile"><div className="value">0</div><div className="label">no events yet</div></div>}
      </div>

      <h2>Event log</h2>
      <div className="card">
        <table>
          <thead><tr><th>Type</th><th>Severity</th><th>Blocked</th><th>Detail</th><th>When</th></tr></thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.id}>
                <td>{e.event_type}</td>
                <td><span className={`badge ${e.severity === "high" ? "danger" : e.severity === "medium" ? "warn" : "neutral"}`}>{e.severity}</span></td>
                <td>{e.blocked ? <span className="badge danger">blocked</span> : <span className="badge neutral">logged</span>}</td>
                <td style={{ maxWidth: 420, whiteSpace: "normal" }}>{e.detail}</td>
                <td>{new Date(e.created_at).toLocaleString()}</td>
              </tr>
            ))}
            {events.length === 0 && <tr><td colSpan={5} style={{ color: "var(--muted)" }}>No security events yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
