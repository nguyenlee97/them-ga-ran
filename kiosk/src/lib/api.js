const BASE = import.meta.env.VITE_API_URL || "";

async function req(path, opts = {}) {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.error || res.statusText), { data });
  return data;
}

export const api = {
  getMenu: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return req(`/api/menu${q ? "?" + q : ""}`);
  },
  getCategories: () => req("/api/menu/categories"),
  login: (phone, code) => req("/api/auth/login", { method: "POST", body: { phone, code } }),
  createCart: (body) => req("/api/carts", { method: "POST", body }),
  getCart: (id) => req(`/api/carts/${id}`),
  addItem: (id, body) => req(`/api/carts/${id}/items`, { method: "POST", body }),
  removeItem: (id, lineId) => req(`/api/carts/${id}/items/${lineId}`, { method: "DELETE" }),
  patchCart: (id, body) => req(`/api/carts/${id}`, { method: "PATCH", body }),
  applyVoucher: (id, code) => req(`/api/vouchers/carts/${id}/apply`, { method: "POST", body: { code } }),
  placeOrder: (body) => req("/api/orders", { method: "POST", body }),
  recommend: (body) => req("/api/recommend", { method: "POST", body }),
  loyalty: (userId) => req(`/api/loyalty/${userId}`),
  logEvent: (body) => req("/api/events", { method: "POST", body }).catch(() => {}),
};
