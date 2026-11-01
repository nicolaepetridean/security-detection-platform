// Thin fetch wrapper. Token is kept in localStorage and attached to every request.
// All calls go through the Vite proxy at /api -> backend.

const BASE = "/api";

export function getToken() {
  return localStorage.getItem("token");
}

export function setToken(token) {
  if (token) localStorage.setItem("token", token);
  else localStorage.removeItem("token");
}

async function request(path, { method = "GET", body, form } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let payload;
  if (form) {
    payload = new URLSearchParams(form);
    headers["Content-Type"] = "application/x-www-form-urlencoded";
  } else if (body !== undefined) {
    payload = JSON.stringify(body);
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${BASE}${path}`, { method, headers, body: payload });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail = data?.detail || res.statusText;
    const err = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    err.status = res.status;
    throw err;
  }
  return data;
}

export const api = {
  login: (username, password) =>
    request("/auth/login", { method: "POST", form: { username, password } }),
  me: () => request("/auth/me"),

  queue: () => request("/detections/queue"),
  activeDetection: () => request("/detections/active"),
  listDetections: (params = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== "" && v != null)
    ).toString();
    return request(`/detections${qs ? `?${qs}` : ""}`);
  },
  claim: (id) => request(`/detections/${id}/claim`, { method: "POST" }),
  close: (id, resolution) =>
    request(`/detections/${id}/close`, { method: "POST", body: { resolution } }),

  customers: () => request("/customers"),
  createCustomer: (body) => request("/customers", { method: "POST", body }),
  updateCustomer: (id, body) =>
    request(`/customers/${id}`, { method: "PATCH", body }),

  signatures: () => request("/signatures"),
  createSignature: (body) => request("/signatures", { method: "POST", body }),
  updateSignature: (id, body) =>
    request(`/signatures/${id}`, { method: "PATCH", body }),

  // Convenience for demos: push a synthetic incident through ingestion.
  ingest: (body) => request("/ingest", { method: "POST", body }),
};
