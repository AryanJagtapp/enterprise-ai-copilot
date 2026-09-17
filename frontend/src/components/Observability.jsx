import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Observability() {
  const [events, setEvents] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.observability(100).then(setEvents).catch((e) => setError(e.message));
  }, []);

  return (
    <div>
      <h1>Observability</h1>
      <div className="subtitle">Per-request latency breakdown, routing decisions, and fallback events.</div>
      {error && <div className="error-banner">{error}</div>}

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Request</th><th>Router</th><th>Strategy</th><th>Prompt version</th>
              <th>Total</th><th>Retrieval</th><th>Rerank</th><th>LLM</th><th>Fallback</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.request_id}>
                <td style={{ fontFamily: "monospace" }}>{e.request_id.slice(0, 8)}</td>
                <td>{e.router_decision || "—"}</td>
                <td>{e.retrieval_strategy || "—"}</td>
                <td style={{ fontFamily: "monospace", fontSize: 11 }}>{e.prompt_version || "—"}</td>
                <td>{e.total_latency_ms ? `${e.total_latency_ms.toFixed(0)}ms` : "—"}</td>
                <td>{e.retrieval_latency_ms ? `${e.retrieval_latency_ms.toFixed(0)}ms` : "—"}</td>
                <td>{e.rerank_latency_ms ? `${e.rerank_latency_ms.toFixed(0)}ms` : "—"}</td>
                <td>{e.llm_latency_ms ? `${e.llm_latency_ms.toFixed(0)}ms` : "—"}</td>
                <td>{e.fallback_triggered ? <span className="badge warn" title={e.fallback_reason}>yes</span> : <span className="badge neutral">no</span>}</td>
              </tr>
            ))}
            {events.length === 0 && <tr><td colSpan={9} style={{ color: "var(--muted)" }}>No requests observed yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
