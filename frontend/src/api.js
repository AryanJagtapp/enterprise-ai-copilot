const API_PREFIX = "/api/v1";

async function request(path, options = {}) {
  const resp = await fetch(`${API_PREFIX}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const isJson = resp.headers.get("content-type")?.includes("application/json");
  const body = isJson ? await resp.json() : await resp.text();
  if (!resp.ok) {
    const message = typeof body === "object" ? body.detail?.message || body.message || JSON.stringify(body) : body;
    throw new Error(message || `Request to ${path} failed with ${resp.status}`);
  }
  return body;
}

export const api = {
  health: () => request("/health"),

  chat: (message, opts = {}) =>
    request("/chat", { method: "POST", body: JSON.stringify({ message, ...opts }) }),

  search: (query, opts = {}) =>
    request("/search", { method: "POST", body: JSON.stringify({ query, ...opts }) }),

  listDocuments: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/documents${qs ? `?${qs}` : ""}`);
  },

  uploadDocument: (file, metadata) => {
    const form = new FormData();
    form.append("file", file);
    Object.entries(metadata || {}).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") form.append(k, v);
    });
    return fetch(`${API_PREFIX}/documents/upload`, { method: "POST", body: form }).then(async (resp) => {
      const body = await resp.json();
      if (!resp.ok) throw new Error(body.detail?.message || "Upload failed");
      return body;
    });
  },

  deleteDocument: (id) => request(`/documents/${id}`, { method: "DELETE" }),

  listPrompts: (promptId) => request(`/prompts${promptId ? `?prompt_id=${promptId}` : ""}`),
  createPromptVersion: (payload) => request("/prompts", { method: "POST", body: JSON.stringify(payload) }),
  activatePrompt: (promptId, version) => request(`/prompts/${promptId}/activate?version=${version}`, { method: "POST" }),
  rollbackPrompt: (promptId, version) => request(`/prompts/${promptId}/rollback?version=${version}`, { method: "POST" }),

  securityEvents: (limit = 50) => request(`/security/events?limit=${limit}`),
  observability: (limit = 50) => request(`/observability?limit=${limit}`),

  runEvaluation: (runLabel) => request("/evaluate", { method: "POST", body: JSON.stringify({ run_label: runLabel }) }),
  compareRuns: (baselineLabel, candidateLabel, threshold = 0.1) =>
    request("/evaluate/compare", { method: "POST", body: JSON.stringify({ baseline_label: baselineLabel, candidate_label: candidateLabel, threshold }) }),
  evaluatePromptChange: (payload) => request("/evaluate/prompt-change", { method: "POST", body: JSON.stringify(payload) }),
  metrics: (runLabel) => request(`/metrics${runLabel ? `?run_label=${runLabel}` : ""}`),
};
