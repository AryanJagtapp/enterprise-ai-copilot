import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Dashboard() {
  const [health, setHealth] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [observability, setObservability] = useState([]);
  const [securityEvents, setSecurityEvents] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([api.health(), api.listDocuments(), api.observability(20), api.securityEvents(20)])
      .then(([h, docs, obs, sec]) => {
        setHealth(h);
        setDocuments(docs);
        setObservability(obs);
        setSecurityEvents(sec);
      })
      .catch((e) => setError(e.message));
  }, []);

  const indexed = documents.filter((d) => d.status === "indexed").length;
  const failed = documents.filter((d) => d.status === "failed").length;
  const fallbacks = observability.filter((o) => o.fallback_triggered).length;
  const avgLatency = observability.length
    ? Math.round(observability.reduce((sum, o) => sum + (o.total_latency_ms || 0), 0) / observability.length)
    : 0;

  return (
    <div>
      <h1>System Dashboard</h1>
      <div className="subtitle">Live status pulled directly from the running backend — nothing here is mocked.</div>

      {error && <div className="error-banner">{error}</div>}

      <div className="grid">
        <div className="stat-tile">
          <div className="value">{health ? <span className="badge ok">ONLINE</span> : <span className="badge danger">OFFLINE</span>}</div>
          <div className="label">Backend health</div>
        </div>
        <div className="stat-tile">
          <div className="value">{documents.length}</div>
          <div className="label">Documents ({indexed} indexed, {failed} failed)</div>
        </div>
        <div className="stat-tile">
          <div className="value">{observability.length}</div>
          <div className="label">Requests observed (last 20)</div>
        </div>
        <div className="stat-tile">
          <div className="value">{avgLatency} ms</div>
          <div className="label">Avg request latency</div>
        </div>
        <div className="stat-tile">
          <div className="value">{fallbacks}</div>
          <div className="label">Fallbacks triggered</div>
        </div>
        <div className="stat-tile">
          <div className="value">{securityEvents.length}</div>
          <div className="label">Security events (last 20)</div>
        </div>
      </div>

      <h2>Recent requests</h2>
      <div className="card">
        <table>
          <thead>
            <tr><th>Route</th><th>Strategy</th><th>Tool</th><th>Fallback</th><th>Latency</th></tr>
          </thead>
          <tbody>
            {observability.slice(0, 8).map((o) => (
              <tr key={o.request_id}>
                <td>{o.router_decision || "—"}</td>
                <td>{o.retrieval_strategy || "—"}</td>
                <td>{o.tool_selected || "—"}</td>
                <td>{o.fallback_triggered ? <span className="badge warn">yes</span> : <span className="badge neutral">no</span>}</td>
                <td>{o.total_latency_ms ? `${o.total_latency_ms.toFixed(1)} ms` : "—"}</td>
              </tr>
            ))}
            {observability.length === 0 && (
              <tr><td colSpan={5} style={{ color: "var(--muted)" }}>No requests yet — try the Chat tab.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
