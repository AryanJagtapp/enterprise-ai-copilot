import React, { useEffect, useState } from "react";
import { api } from "../api.js";

const CONFIDENTIALITY_LEVELS = ["Public", "Internal", "Confidential", "Restricted"];

export default function Documents() {
  const [documents, setDocuments] = useState([]);
  const [error, setError] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [form, setForm] = useState({
    document_type: "",
    client_name: "",
    business_unit: "",
    department: "",
    confidentiality_level: "Internal",
    tags: "",
  });
  const [file, setFile] = useState(null);

  function refresh() {
    api.listDocuments().then(setDocuments).catch((e) => setError(e.message));
  }

  useEffect(refresh, []);

  async function handleUpload(e) {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await api.uploadDocument(file, form);
      setFile(null);
      refresh();
    } catch (e2) {
      setError(e2.message);
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(id) {
    try {
      await api.deleteDocument(id);
      refresh();
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div>
      <h1>Documents</h1>
      <div className="subtitle">Upload PDF/DOCX/TXT files with enterprise metadata for filtering and access control.</div>

      {error && <div className="error-banner">{error}</div>}

      <div className="card">
        <form onSubmit={handleUpload}>
          <div className="row" style={{ marginBottom: 10 }}>
            <input type="file" accept=".pdf,.docx,.txt" onChange={(e) => setFile(e.target.files[0])} />
            <input placeholder="document_type" value={form.document_type} onChange={(e) => setForm({ ...form, document_type: e.target.value })} />
            <input placeholder="client_name" value={form.client_name} onChange={(e) => setForm({ ...form, client_name: e.target.value })} />
          </div>
          <div className="row" style={{ marginBottom: 10 }}>
            <select value={form.business_unit} onChange={(e) => setForm({ ...form, business_unit: e.target.value })}>
              <option value="">business_unit...</option>
              <option value="CD">CD</option>
              <option value="FD">FD</option>
              <option value="shared">shared</option>
            </select>
            <input placeholder="department" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} />
            <select value={form.confidentiality_level} onChange={(e) => setForm({ ...form, confidentiality_level: e.target.value })}>
              {CONFIDENTIALITY_LEVELS.map((l) => <option key={l}>{l}</option>)}
            </select>
            <input placeholder="tags (comma separated)" value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} />
          </div>
          <button className="btn" type="submit" disabled={!file || uploading}>
            {uploading ? "Uploading..." : "Upload"}
          </button>
        </form>
      </div>

      <h2>Indexed documents ({documents.length})</h2>
      <div className="card">
        <table>
          <thead>
            <tr><th>Filename</th><th>Type</th><th>BU</th><th>Confidentiality</th><th>Status</th><th>Chunks</th><th></th></tr>
          </thead>
          <tbody>
            {documents.map((d) => (
              <tr key={d.document_id}>
                <td>{d.filename}</td>
                <td>{d.document_type || "—"}</td>
                <td>{d.business_unit || "—"}</td>
                <td>
                  <span className={`badge ${d.confidentiality_level === "Restricted" ? "danger" : d.confidentiality_level === "Confidential" ? "warn" : "neutral"}`}>
                    {d.confidentiality_level}
                  </span>
                </td>
                <td>
                  <span className={`badge ${d.status === "indexed" ? "ok" : d.status === "failed" ? "danger" : "warn"}`}>{d.status}</span>
                </td>
                <td>{d.chunk_count}</td>
                <td><button className="btn secondary" onClick={() => handleDelete(d.document_id)}>Delete</button></td>
              </tr>
            ))}
            {documents.length === 0 && (
              <tr><td colSpan={7} style={{ color: "var(--muted)" }}>No documents uploaded yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
