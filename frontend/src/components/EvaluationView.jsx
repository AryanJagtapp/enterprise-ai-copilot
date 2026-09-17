import React, { useState } from "react";
import { api } from "../api.js";

export default function EvaluationView() {
  const [runLabel, setRunLabel] = useState("");
  const [results, setResults] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState(null);
  const [running, setRunning] = useState(false);

  async function runNow() {
    setRunning(true);
    setError(null);
    try {
      const label = runLabel || undefined;
      const resp = await api.runEvaluation(label);
      setResults(resp);
      const all = await api.metrics(resp.run_label);
      setHistory(all);
    } catch (e) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div>
      <h1>Evaluation</h1>
      <div className="subtitle">
        Runs the real benchmark suite against the live pipeline — retrieval hit-rate, citation presence, safety-case
        pass rate, tool reliability, and retrieval latency. Regression detection compares two runs and can trigger a
        prompt rollback (see the Evaluate → Compare / Prompt-Change endpoints in Swagger for the full workflow).
      </div>
      {error && <div className="error-banner">{error}</div>}

      <div className="card row">
        <input placeholder="run label (optional)" value={runLabel} onChange={(e) => setRunLabel(e.target.value)} />
        <button className="btn" onClick={runNow} disabled={running}>{running ? "Running..." : "Run evaluation now"}</button>
      </div>

      {results && (
        <>
          <h2>Run: {results.run_label}</h2>
          <div className="grid">
            {results.metrics.map((m) => (
              <div className="stat-tile" key={m.name}>
                <div className="value">{typeof m.value === "number" ? m.value.toFixed(3) : m.value}</div>
                <div className="label">{m.name.replace(/_/g, " ")}</div>
              </div>
            ))}
          </div>
        </>
      )}

      {history.length > 0 && (
        <>
          <h2>Metric history for this run</h2>
          <div className="card">
            <table>
              <thead><tr><th>Metric</th><th>Value</th><th>Baseline</th><th>Regression?</th></tr></thead>
              <tbody>
                {history.map((h, i) => (
                  <tr key={i}>
                    <td>{h.metric_name}</td>
                    <td>{h.metric_value.toFixed(3)}</td>
                    <td>{h.baseline_value !== null ? h.baseline_value.toFixed(3) : "—"}</td>
                    <td>{h.regression_detected ? <span className="badge danger">regression</span> : <span className="badge ok">ok</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
