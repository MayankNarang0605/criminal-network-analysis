/**
 * API client.
 *
 * Single place that talks to the backend. Holds the bearer token in
 * sessionStorage (not localStorage) so it does not survive the browser session,
 * which is the appropriate lifetime for a law-enforcement console.
 */
const BASE = "/api/v1";

let token = sessionStorage.getItem("ncrb_token") || "";
let user = JSON.parse(sessionStorage.getItem("ncrb_user") || "null");

export function getUser() {
  return user;
}

export function isAuthenticated() {
  return Boolean(token);
}

function headers(extra = {}) {
  const h = { "Content-Type": "application/json", ...extra };
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

async function handle(res) {
  if (res.status === 401) {
    logout();
    throw new Error("Session expired. Please sign in again.");
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      detail = body.detail || body.error || detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function get(path) {
  return handle(await fetch(`${BASE}${path}`, { headers: headers() }));
}

export async function post(path, body) {
  return handle(
    await fetch(`${BASE}${path}`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify(body ?? {}),
    })
  );
}

export async function put(path, body) {
  return handle(
    await fetch(`${BASE}${path}`, {
      method: "PUT",
      headers: headers(),
      body: JSON.stringify(body ?? {}),
    })
  );
}

export async function login(username, password) {
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const data = await handle(res);
  token = data.access_token;
  user = data.user;
  sessionStorage.setItem("ncrb_token", token);
  sessionStorage.setItem("ncrb_user", JSON.stringify(user));
  return data;
}

export function logout() {
  token = "";
  user = null;
  sessionStorage.removeItem("ncrb_token");
  sessionStorage.removeItem("ncrb_user");
}

// ---- Endpoint helpers -----------------------------------------------------
export const api = {
  health: () => fetch("/health").then((r) => r.json()),
  dashboard: () => get("/dashboard/summary"),
  geo: () => get("/dashboard/geo"),
  stats: () => get("/data/stats"),

  cases: (params = "") => get(`/data/cases${params}`),
  caseDetail: (id) => get(`/data/cases/${encodeURIComponent(id)}`),
  cdr: (params = "?limit=100") => get(`/data/cdr${params}`),
  transactions: (params = "?limit=100") => get(`/data/transactions${params}`),

  graphOverview: (personOnly = true, limit = 400) =>
    get(`/graph/overview?person_only=${personOnly}&limit=${limit}`),
  entity: (id, depth = 1) =>
    get(`/graph/entity/${encodeURIComponent(id)}?depth=${depth}`),
  entities: (params = "?limit=100") => get(`/graph/entities${params}`),
  kingpins: (n = 20) => get(`/graph/kingpins?top_n=${n}`),
  communities: () => get("/graph/communities"),
  path: (source, target, k = 3) =>
    get(
      `/graph/path?source=${encodeURIComponent(source)}&target=${encodeURIComponent(
        target
      )}&k=${k}`
    ),
  predictLinks: (n = 25) => get(`/graph/predict-links?top_n=${n}`),
  simulate: (entityIds) => post("/graph/simulate-disruption", { entity_ids: entityIds }),
  optimalDisruption: (budget = 3) => get(`/graph/optimal-disruption?budget=${budget}`),

  risk: (limit = 50) => get(`/ml/risk?limit=${limit}`),
  riskDetail: (id) => get(`/ml/risk/${encodeURIComponent(id)}`),
  patterns: (params = "?limit=150") => get(`/ml/patterns${params}`),
  evaluation: () => get("/ml/evaluation"),

  search: (q, refType) =>
    get(`/search?q=${encodeURIComponent(q)}${refType ? `&ref_type=${refType}` : ""}`),
  suggest: (q) => get(`/search/suggest?q=${encodeURIComponent(q)}`),

  alerts: (params = "?limit=100") => get(`/alerts${params}`),

  auditChain: (limit = 30) => get(`/audit/chain?limit=${limit}`),
  auditVerify: () => get("/audit/verify"),
  auditStats: () => get("/audit/stats"),
  auditProof: (idx) => get(`/audit/proof/${idx}`),
  tamperDemo: (idx = 1) => post("/audit/tamper-demo", { idx }),

  womenSafety: () => get("/women-safety/dashboard"),
  repeatOffenders: () => get("/women-safety/repeat-offenders"),
  escalation: () => get("/women-safety/escalation-watchlist"),
  corridors: () => get("/women-safety/trafficking-corridors"),

  extract: (text) => post("/nlp/extract", { text }),
  ingest: (networks = 6) =>
    post(`/data/ingest?synthetic_networks=${networks}&use_samples=true`),

  // Live investigation — additive ingest from dashboard, no wipe
  addCase: (fir) => post("/data/case", fir),
  addCdrBatch: (records) => post("/data/cdr/batch", { records }),
  addTransactionsBatch: (records) => post("/data/transactions/batch", { records }),

  // Case editing — admin only, versioned (all fields including fir_id)
  updateCase: (id, fir) => put(`/data/cases/${encodeURIComponent(id)}`, fir),
  caseHistory: (id) => get(`/data/cases/${encodeURIComponent(id)}/history`),
};
