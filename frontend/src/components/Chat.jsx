import React, { useState } from "react";
import { api } from "../api.js";

/**
 * Minimal, dependency-free Markdown renderer for model answers.
 *
 * Deliberately NOT using a Markdown library + dangerouslySetInnerHTML:
 * the text being rendered here is LLM output derived from retrieved
 * documents, which this project's whole Security Gateway treats as
 * untrusted content (see app/security/injection.py's wrap_as_untrusted_data
 * docstring on the backend). Rendering that as raw HTML would reopen
 * exactly the kind of injection surface the backend goes out of its way
 * to guard against. This renderer only ever produces real React elements
 * from a small, explicit set of Markdown constructs (headers, bold,
 * bullet lists, horizontal rules, paragraphs) — there is no code path
 * that turns model output into raw HTML.
 */
function renderInline(text, keyPrefix) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) =>
    part.startsWith("**") && part.endsWith("**") && part.length > 4 ? (
      <strong key={`${keyPrefix}-b-${i}`}>{part.slice(2, -2)}</strong>
    ) : (
      <React.Fragment key={`${keyPrefix}-t-${i}`}>{part}</React.Fragment>
    )
  );
}

function renderMarkdown(text) {
  const lines = String(text ?? "").split("\n");
  const blocks = [];
  let listBuffer = [];
  let paraBuffer = [];

  function flushList(key) {
    if (listBuffer.length) {
      blocks.push(
        <ul key={`ul-${key}`} style={{ margin: "4px 0 8px 20px", padding: 0 }}>
          {listBuffer.map((item, i) => (
            <li key={i}>{renderInline(item, `li-${key}-${i}`)}</li>
          ))}
        </ul>
      );
      listBuffer = [];
    }
  }

  function flushPara(key) {
    if (paraBuffer.length) {
      blocks.push(
        <p key={`p-${key}`} style={{ margin: "4px 0" }}>
          {renderInline(paraBuffer.join(" "), `p-${key}`)}
        </p>
      );
      paraBuffer = [];
    }
  }

  lines.forEach((rawLine, idx) => {
    const line = rawLine.trim();

    if (line === "") {
      flushPara(idx);
      flushList(idx);
      return;
    }
    if (line === "---" || line === "***") {
      flushPara(idx);
      flushList(idx);
      blocks.push(<hr key={`hr-${idx}`} style={{ border: "none", borderTop: "1px solid var(--panel-border)", margin: "8px 0" }} />);
      return;
    }
    const headerMatch = line.match(/^(#{1,4})\s+(.*)$/);
    if (headerMatch) {
      flushPara(idx);
      flushList(idx);
      const level = headerMatch[1].length;
      const Tag = `h${Math.min(level + 2, 6)}`; // keep headers modest-sized inside a chat bubble
      blocks.push(
        React.createElement(Tag, { key: `h-${idx}`, style: { margin: "10px 0 4px" } }, renderInline(headerMatch[2], `h-${idx}`))
      );
      return;
    }
    const listMatch = line.match(/^[*-]\s+(.*)$/);
    if (listMatch) {
      flushPara(idx);
      listBuffer.push(listMatch[1]);
      return;
    }
    flushList(idx);
    paraBuffer.push(line);
  });
  flushPara("end");
  flushList("end");

  return blocks;
}

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
              <div>{renderMarkdown(m.response.answer)}</div>
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

export { renderMarkdown };
