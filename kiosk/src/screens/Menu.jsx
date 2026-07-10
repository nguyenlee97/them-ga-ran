import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api.js";
import { vnd } from "../lib/format.js";
import ItemModal from "../components/ItemModal.jsx";

export default function Menu(props) {
  const { t, lang, setLang, dineMode, setDineMode, cart, refreshCart, recoContext, onViewCart, onHome } = props;
  const [items, setItems] = useState([]);
  const [activeCat, setActiveCat] = useState(null);
  const [modal, setModal] = useState(null);
  const [bannerOk, setBannerOk] = useState(true);

  useEffect(() => {
    api.getMenu().then((d) => {
      setItems(d.items || []);
      setActiveCat(d.items?.[0]?.category || null);
    });
  }, []);

  // preserve scrape order (items come sorted by sortOrder)
  const categories = useMemo(() => {
    const seen = []; for (const i of items) if (!seen.includes(i.category)) seen.push(i.category);
    return seen;
  }, [items]);
  const shown = items.filter((i) => i.category === activeCat);

  const add = async (productId) => {
    const prod = items.find((i) => i._id === productId);
    await api.addItem(cart._id, { productId, qty: 1 });
    await refreshCart();
    setModal({ name: prod?.name_vi });
  };
  const upgrade = async (combo) => {
    const covered = new Set(combo.covers || []);
    const fresh = await api.getCart(cart._id);
    for (const l of fresh.items || []) if (covered.has(l.sku)) await api.removeItem(cart._id, l.lineId);
    await api.addItem(cart._id, { productId: combo.productId, qty: 1 });
    await refreshCart();
    setModal(null);
  };

  const count = cart?.items?.reduce((s, l) => s + l.qty, 0) || 0;

  return (
    <div className="flex-1 flex flex-col pb-20 bg-white">
      {/* Promo banner — /assets/menu-banner.png (1080×264) */}
      <div className="px-3 pt-3">
        {bannerOk ? (
          <img src="/assets/menu-banner.png" alt="KFC Rewards" onError={() => setBannerOk(false)}
            className="w-full rounded-xl object-cover" />
        ) : (
          <div className="rounded-xl bg-kfcred text-white px-4 py-3 flex items-center justify-between">
            <div>
              <div className="text-[10px] font-bold tracking-widest opacity-90">KFC REWARDS</div>
              <div className="font-black leading-tight">ĐĂNG KÝ THÀNH VIÊN<br /><span className="text-sm font-semibold">MỞ KHÓA ƯU ĐÃI</span></div>
            </div>
            <div className="text-right"><div className="text-3xl font-black">3·5·7%</div><div className="text-[10px]">Tích điểm theo hạng</div></div>
          </div>
        )}
      </div>

      {/* Control row: dine toggle + lang + search */}
      <div className="px-3 py-2 flex items-center gap-2">
        <button onClick={() => setDineMode("dine_in")}
          className={`px-3 py-1.5 rounded-full text-sm border ${dineMode === "dine_in" ? "border-kfcred text-kfcred font-semibold" : "border-gray-200 text-gray-500"}`}>
          🍽️ {t("dineIn")}
        </button>
        <button onClick={() => setDineMode("takeaway")}
          className={`px-3 py-1.5 rounded-full text-sm border ${dineMode === "takeaway" ? "border-kfcred text-kfcred font-semibold" : "border-gray-200 text-gray-500"}`}>
          🥡 {t("takeaway")}
        </button>
        <div className="ml-auto flex items-center gap-2">
          <select value={lang} onChange={(e) => setLang(e.target.value)}
            className="border border-gray-200 rounded-lg text-sm px-2 py-1.5 text-gray-600">
            <option value="vi">VI</option><option value="en">EN</option>
          </select>
          <div className="w-9 h-9 rounded-lg border border-gray-200 flex items-center justify-center text-gray-400">🔍</div>
        </div>
      </div>

      {/* Body: category rail + cards */}
      <div className="flex flex-1 min-h-0">
        <div className="w-28 shrink-0 border-r border-gray-100 overflow-y-auto">
          {categories.map((c) => (
            <button key={c} onClick={() => setActiveCat(c)}
              className={`w-full text-left px-3 py-3 text-[13px] leading-tight ${
                activeCat === c ? "bg-kfcred text-white font-bold" : "text-gray-600"}`}>
              {c}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto">
          <h2 className="px-3 pt-3 pb-1 font-black text-kfcred uppercase">{activeCat}</h2>
          <div className="grid grid-cols-2 gap-3 p-3">
            {shown.map((it) => (
              <div key={it._id} className="border border-gray-200 rounded-xl overflow-hidden flex flex-col">
                <div className="h-28 bg-gray-50">
                  {it.imageUrl
                    ? <img src={it.imageUrl} alt={it.name_vi} className="w-full h-full object-cover" loading="lazy" />
                    : <div className="w-full h-full flex items-center justify-center text-3xl">🍗</div>}
                </div>
                <div className="p-2 flex flex-col flex-1">
                  <div className="text-[13px] font-semibold leading-tight line-clamp-2">{it.name_vi}</div>
                  <div className="mt-1 flex items-baseline gap-1">
                    <span className="text-kfcred font-bold text-sm">{vnd(it.price)}</span>
                    {it.oldPrice ? <span className="text-[11px] text-gray-400 line-through">{vnd(it.oldPrice)}</span> : null}
                  </div>
                  {it.description ? <div className="text-[11px] text-gray-400 line-clamp-2 mt-0.5">{it.description}</div> : null}
                  <button onClick={() => add(it._id)}
                    className="mt-2 bg-kfcred text-white text-sm rounded-lg py-1.5 font-semibold">+ {t("add")}</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[480px] bg-white border-t border-gray-200 px-3 py-2 flex items-center gap-2">
        <div className="relative text-2xl">🪣<span className="absolute -top-1 -right-1 bg-kfcred text-white text-[10px] rounded-full w-4 h-4 flex items-center justify-center">{count}</span></div>
        <button onClick={onHome} className="border border-gray-300 rounded-full px-3 py-2 text-sm text-gray-600">{t("home")}</button>
        <div className="ml-auto text-right mr-1">
          <div className="text-[10px] text-gray-500">{t("total")}</div>
          <div className="text-sm font-black text-kfcred">{vnd(cart?.totals?.grandTotal)}</div>
        </div>
        <button onClick={onViewCart} disabled={!count}
          className="bg-kfcred text-white rounded-full px-4 py-2.5 font-bold text-sm disabled:opacity-40">{t("viewCart")}</button>
      </div>

      {modal && (
        <ItemModal t={t} addedName={modal.name} context={recoContext()} onAdd={add} onUpgrade={upgrade}
          onContinue={() => setModal(null)} onViewCart={() => { setModal(null); onViewCart(); }} />
      )}
    </div>
  );
}
