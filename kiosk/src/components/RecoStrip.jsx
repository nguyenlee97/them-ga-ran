import { useEffect, useState } from "react";
import { api } from "../lib/api.js";
import { vnd } from "../lib/format.js";

/**
 * The AI recommendation surface — one component reused at every "moment"
 * (item_added modal, cart page, checkout). Calls POST /api/recommend with the
 * given slot + context, renders cards with the LLM/template copy + reason, and
 * logs reco_accepted when the user adds a suggestion.
 */
export default function RecoStrip({ slot, context, title, t, onAdd, limit = 3, compact = false }) {
  const [recs, setRecs] = useState([]);
  const [explain, setExplain] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    api
      .recommend({ slot, context, limit })
      .then((r) => {
        if (!alive) return;
        setRecs(r.recommendations || []);
        setExplain(r.explain || null);
      })
      .catch(() => alive && setRecs([]))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [slot, JSON.stringify(context)]);

  if (loading) return <div className="px-4 py-3 text-sm text-gray-400">…</div>;
  if (!recs.length) return null;

  return (
    <div className="px-4 py-3">
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-bold text-kfcdark">{title}</h3>
        {explain?.strategies_used?.length ? (
          <span className="text-[10px] text-gray-400">AI · {explain.strategies_used.join("+")}</span>
        ) : null}
      </div>
      <div className={compact ? "space-y-2" : "flex gap-3 overflow-x-auto pb-1"}>
        {recs.map((r) => (
          <div
            key={r.sku}
            className={
              compact
                ? "flex items-center gap-3 border border-gray-200 rounded-xl p-2"
                : "min-w-[150px] w-[150px] border border-gray-200 rounded-xl p-2 flex flex-col"
            }
          >
            <div className={compact ? "w-14 h-14 shrink-0" : "w-full h-20 mb-1"}>
              {r.imageUrl ? (
                <img src={r.imageUrl} alt={r.name} className="w-full h-full object-cover rounded-lg" />
              ) : (
                <div className="w-full h-full bg-gray-100 rounded-lg flex items-center justify-center text-2xl">🍗</div>
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-semibold truncate">{r.name}</div>
              <div className="text-xs text-kfcred font-bold">{vnd(r.price)}</div>
              {r.copy ? <div className="text-[11px] text-gray-500 line-clamp-2">{r.copy}</div> : null}
            </div>
            <button
              onClick={async () => {
                await onAdd(r.productId);
                api.logEvent({
                  type: "reco_accepted", slot, strategy: r.strategy, channel: "kiosk",
                  cartId: context.cartId, userId: context.userId, productId: r.sku,
                });
              }}
              className="mt-1 bg-kfcred text-white text-sm font-semibold rounded-lg px-3 py-1 shrink-0"
            >
              + {t("add")}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
