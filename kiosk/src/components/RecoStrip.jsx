import { useEffect, useState } from "react";
import { api } from "../lib/api.js";
import { vnd } from "../lib/format.js";

/**
 * The AI recommendation surface — reused at every "moment" (item_added modal,
 * cart, checkout). Renders an optional "Nâng cấp lên Combo" trade-up card plus
 * the complement strip (drink / side / dessert).
 */
export default function RecoStrip({ slot, context, title, t, onAdd, onUpgrade, limit = 3 }) {
  const [recs, setRecs] = useState([]);
  const [combo, setCombo] = useState(null);
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
        setCombo(r.comboUpsell || null);
        setExplain(r.explain || null);
      })
      .catch(() => { if (alive) { setRecs([]); setCombo(null); } })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [slot, JSON.stringify(context)]);

  if (loading) return <div className="px-4 py-3 text-sm text-gray-400">…</div>;
  if (!recs.length && !combo) return null;

  return (
    <div className="px-4 py-3 space-y-3">
      {combo && onUpgrade && (
        <div className="border-2 border-amber-400 bg-amber-50 rounded-2xl p-3 flex items-center gap-3">
          <div className="w-16 h-16 rounded-xl overflow-hidden bg-white shrink-0 flex items-center justify-center text-2xl">
            {combo.imageUrl ? <img src={combo.imageUrl} alt={combo.name} className="w-full h-full object-cover" /> : "🍱"}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[10px] font-black tracking-wide text-amber-600">⬆ NÂNG CẤP LÊN COMBO</div>
            <div className="text-sm font-bold truncate">{combo.name}</div>
            <div className="flex items-baseline gap-2">
              <span className="text-kfcred font-bold">{vnd(combo.price)}</span>
              <span className="text-[11px] text-gray-400 line-through">{vnd(combo.alacartePrice)}</span>
              {combo.priceDelta < 0 && (
                <span className="text-[11px] font-bold text-green-600">−{vnd(-combo.priceDelta)}</span>
              )}
            </div>
            <div className="text-[11px] text-gray-600 line-clamp-2">{combo.copy}</div>
          </div>
          <button onClick={() => {
              onUpgrade(combo);
              api.logEvent({
                type: "combo_upgrade_accepted", slot, channel: "kiosk",
                cartId: context.cartId, userId: context.userId, productId: combo.sku,
                payload: { priceDelta: combo.priceDelta },
              });
            }}
            className="bg-amber-500 text-white text-sm font-bold rounded-lg px-3 py-2 shrink-0">
            Nâng cấp
          </button>
        </div>
      )}

      {recs.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-bold text-kfcdark">{title}</h3>
            {explain?.strategies_used?.length ? (
              <span className="text-[10px] text-gray-400">AI · {explain.strategies_used.join("+")}</span>
            ) : null}
          </div>
          <div className="flex gap-3 overflow-x-auto pb-1">
            {recs.map((r) => (
              <div key={r.sku} className="min-w-[150px] w-[150px] border border-gray-200 rounded-xl p-2 flex flex-col">
                <div className="w-full h-20 mb-1">
                  {r.imageUrl
                    ? <img src={r.imageUrl} alt={r.name} className="w-full h-full object-cover rounded-lg" />
                    : <div className="w-full h-full bg-gray-100 rounded-lg flex items-center justify-center text-2xl">🍗</div>}
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
      )}
    </div>
  );
}
