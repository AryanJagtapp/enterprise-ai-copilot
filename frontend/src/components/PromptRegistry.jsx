import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function PromptRegistry() {
  const [prompts, setPrompts] = useState([]);
  const [error, setError] = useState(null);

  function refresh() {
    api.listPrompts().then(setPrompts).catch((e) => setError(e.message));
  }
  useEffect(refresh, []);

  const grouped = prompts.reduce((acc, p) => {
    acc[p.prompt_id] = acc[p.prompt_id] || [];
    acc[p.prompt_id].push(p);
    return acc;
  }, {});

  async function activate(promptId, version) {
    try {
      await api.activatePrompt(promptId, version);
      refresh();
    } catch (e) {
      setError(e.message);
    }
  }

  async function rollback(promptId, version) {
    try {
      await api.rollbackPrompt(promptId, version);
      refresh();
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div>
      <h1>Prompt Registry</h1>
      <div className="subtitle">Every prompt the system actually uses at runtime — versioned, with activate/rollback.</div>
      {error && <div className="error-banner">{error}</div>}

      {Object.entries(grouped).map(([promptId, versions]) => (
        <div className="card" key={promptId}>
          <h2 style={{ marginTop: 0 }}>{promptId}</h2>
          <table>
            <thead><tr><th>Version</th><th>Status</th><th>Description</th><th>Created</th><th></th></tr></thead>
            <tbody>
              {versions.sort((a, b) => a.version - b.version).map((v) => (
                <tr key={v.id}>
                  <td>v{v.version}</td>
                  <td><span className={`badge ${v.status === "active" ? "ok" : v.status === "retired" ? "neutral" : "warn"}`}>{v.status}</span></td>
                  <td>{v.description}</td>
                  <td>{new Date(v.created_at).toLocaleString()}</td>
                  <td>
                    {v.status !== "active" && (
                      <button className="btn secondary" onClick={() => activate(promptId, v.version)}>Activate</button>
                    )}
                    {v.status === "retired" && (
                      <button className="btn secondary" onClick={() => rollback(promptId, v.version)}>Rollback here</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
      {prompts.length === 0 && <div className="card">No prompts loaded yet.</div>}
    </div>
  );
}
