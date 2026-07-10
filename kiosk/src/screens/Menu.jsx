import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api.js";
import { vnd } from "../lib/format.js";
import Header from "../components/Header.jsx";
import RecoStrip from "../components/RecoStrip.jsx";
import ItemModal from "../components/ItemModal.jsx";

export default function Menu(props) {
  const { t, cart, refreshCart, recoContext, onViewCart } = props;
  const [items, setItems] = useState([]);
  const [activeCat, setActiveCat] = useState(null);
  const [modal, setModal] = useState(null); // {name}
  const [adding, setAdding] = useState(null);

  useEffect(() => {
    api.getMenu().then((d) => {
      setItems(d.items || []);
      setActiveCat((d.items?.[0]?.category) || null);
    });
  }, []);

  const categories = useMemo(
    () => [...new Set(items.map((i) => i.category))],
    [items]
  );
  const featured = useMemo(() => items.filter((i) => i.isCombo).slice(0, 4), [items]);
  const shown = items.filter((i) => i.category === activeCat);

  const add = async (productId) => {
    setAdding(productId);
    const prod = items.find((i) => i._id === productId);
    await api.addItem(cart._id, { productId, qty: 1 });
    await refreshCart();
    setAdding(null);
    setModal({ name: prod?.name_vi || t("add") });
  };

  const count = cart?.items?.reduce((s, l) => s + l.qty, 0) || 0;

  return (
    <div className="flex-1 flex flex-col pb-24">
      <Header {...props} />

      {/* Promo / flash-deal strip */}
      {featured.length > 0 && (
        <div className="px-4 pt-3">
          <h3 className="font-black text-kfcred mb-2">{t("flashDeals")}</h3>
          <div className="flex gap-3 overflow-x-auto pb-1">
            {featured.map((f) => (
              <div key={f._id} className="min-w-[160px] w-[160px] border border-gray-200 rounded-xl p-2">
                <div className="h-20 bg-gray-100 rounded-lg mb-1 flex items-center justify-center text-3xl">🍗</div>
                <div className="text-sm font-semibold line-clamp-2">{f.name_vi}</div>
                <div className="text-kfcred font-bold text-sm">{vnd(f.price)}</div>
                <button onClick={() => add(f._id)}
                  className="mt-1 w-full bg-kfcred text-white text-sm rounded-lg py-1 font-semibold">
                  + {t("add")}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex flex-1 mt-2">
        {/* Category rail */}
        <div className="w-28 shrink-0 border-r border-gray-100">
          {categories.map((c) => (
            <button key={c} onClick={() => setActiveCat(c)}
              className={`w-full text-left px-3 py-3 text-sm ${
                activeCat === c ? "bg-kfcred/10 text-kfcred font-bold border-l-4 border-kfcred" : "text-gray-600"
              }`}>
              {c}
            </button>
          ))}
        </div>

        {/* Item grid */}
        <div className="flex-1">
          <div className="grid grid-cols-2 gap-3 p-3">
            {shown.map((it) => (
              <div key={it._id} className="border border-gray-200 rounded-xl p-2 flex flex-col">
                <div className="h-20 bg-gray-100 rounded-lg mb-1 flex items-center justify-center text-3xl">
                  {it.tags?.includes("drink") ? "🥤" : it.tags?.includes("dessert") ? "🍦" : "🍗"}
                </div>
                <div className="text-sm font-semibold leading-tight line-clamp-2">{it.name_vi}</div>
                <div className="text-kfcred font-bold text-sm mt-auto">{vnd(it.price)}</div>
                <button onClick={() => add(it._id)} disabled={adding === it._id}
                  className="mt-1 bg-kfcred text-white text-sm rounded-lg py-1 font-semibold disabled:opacity-50">
                  + {t("add")}
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Footer: running total + view cart */}
      <div className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[480px] bg-white border-t border-gray-200 px-4 py-3 flex items-center justify-between">
        <div>
          <div className="text-xs text-gray-500">{t("total")}</div>
          <div className="text-lg font-black text-kfcred">{vnd(cart?.totals?.grandTotal)}</div>
        </div>
        <button onClick={onViewCart} disabled={!count}
          className="bg-kfcred text-white rounded-full px-6 py-3 font-bold disabled:opacity-40">
          🛒 {t("viewCart")} ({count})
        </button>
      </div>

      {modal && (
        <ItemModal
          t={t} addedName={modal.name} context={recoContext()} onAdd={add}
          onContinue={() => setModal(null)}
          onViewCart={() => { setModal(null); onViewCart(); }}
        />
      )}
    </div>
  );
}
