/**
 * Thin proxy to the FastAPI reco service. Backend exposes /api/recommend so the
 * kiosk and chat agent hit ONE surface; this forwards to the Python service and
 * degrades gracefully (empty recs) if it's unavailable.
 */
const RECO_URL = process.env.RECO_URL || "http://localhost:8080";

export async function getRecommendations(body, { timeoutMs = 8000 } = {}) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const resp = await fetch(`${RECO_URL}/recommend`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: ctrl.signal,
    });
    if (!resp.ok) return { recommendations: [], explain: { error: `reco_${resp.status}` } };
    return await resp.json();
  } catch (e) {
    // Never block the ordering flow on a reco failure.
    return { recommendations: [], explain: { error: "reco_unavailable", detail: String(e).slice(0, 120) } };
  } finally {
    clearTimeout(t);
  }
}
