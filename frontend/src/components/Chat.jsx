import React, { useState } from "react";
import { api } from "../api.js";

function traceLine(response) {
  const steps = ["Query", `Router: ${response.router_decision}`];
  if (response.retrieval_strategy) steps.push(response.retrieval_strategy);
  if (response.tools_used?.length) steps.push(`Tool: ${response.tools_used.join(", ")}`);
  if (response.sub_questions?.length) steps.push(`${response.sub_questions.length} sub-questions`);
  steps.push(response.citations?.length ? `${response.citations.length} sources selected` : "no sources");
  if (response.fallback_triggered) steps.push("⚠ fallback used");
  steps.push("Response");
  return steps.join("  →  ");
}

export default function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [clearance, setClearance] = useState("Internal");
  const [businessUnit, setBusinessUnit] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function send() {
    if (!input.trim()) return;
    const userMessage = input;
    setMessages((m) => [...m, { role: "user", text: userMessage }]);
    setInput("");
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch("/api/v1/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-User-Clearance": clearance },
        body: JSON.stringify({ message: userMessage, business_unit: businessUnit || undefined }),
      });
      const body = await resp.json();
      if (!resp.ok) throw new Error(body.detail?.message || "Request failed");
      setMessages((m) => [...m, { role: "assistant", response: body }]);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1>Chat</h1>
      <div className="subtitle">
        Every message passes through the Security Gateway, the Adaptive Orchestrator, and (for RAG/multi-hop) real
        hybrid retrieval + reranking + Gemini synthesis with automatic fallback.
      </div>

      <div className="card row" style={{ marginBottom: 16 }}>
        <label style={{ fontSize: 12, color: "var(--muted)" }}>
          Clearance
          <br />
          <select value={clearance} onChange={(e) => setClearance(e.target.value)}>
            <option>Public</option>
            <option>Internal</option>
            <option>Confidential</option>
            <option>Restricted</option>
          </select>
        </label>
        <label style={{ fontSize: 12, color: "var(--muted)" }}>
          Business unit filter
          <br />
          <select value={businessUnit} onChange={(e) => setBusinessUnit(e.target.value)}>
            <option value="">All</option>
            <option value="CD">CD</option>
            <option value="FD">FD</option>
            <option value="shared">shared</option>
          </select>
        </label>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="chat-log">
        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="chat-bubble user">{m.text}</div>
          ) : (
            <div key={i} className="chat-bubble assistant">
              <div>{m.response.answer}</div>
              {m.response.citations?.length > 0 && (
                <div>
                  {m.response.citations.map((c, j) => (
                    <span key={j} className="citation-chip">{c}</span>
                  ))}
                </div>
              )}
              <div className="trace-line">{traceLine(m.response)}</div>
              {m.response.fallback_reasons?.length > 0 && (
                <div className="trace-line" style={{ color: "var(--warning)" }}>
                  {m.response.fallback_reasons.join(" | ")}
                </div>
              )}
            </div>
          )
        )}
      </div>

      <div className="row">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          placeholder="Ask a question, request a calculation, or try an edge case..."
          style={{ flex: 1 }}
        />
        <button className="btn" onClick={send} disabled={loading}>
          {loading ? "Sending..." : "Send"}
        </button>
      </div>
    </div>
  );
}
