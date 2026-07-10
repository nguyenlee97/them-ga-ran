import { useState } from "react";
import { api } from "../lib/api.js";
import { vnd } from "../lib/format.js";
import RecoStrip from "../components/RecoStrip.jsx";

export default function Cart(props) {
  const { t, dineMode, setDineMode, user, cart, refreshCart, recoContext, onBack, onCheckout, openLogin } = props;
  const [showCode, setShowCode] = useState(false);
  const [code, setCode] = useState("");
  const [voucherMsg, setVoucherMsg] = useState("");

  const addReco = async (productId) => { await api.addItem(cart._id, { productId, qty: 1 }); await refreshCart(); };
  const upgrade = async (combo) => {
    // trade-up: replace the covered à-la-carte lines with the combo
    const covered = new Set(combo.covers || []);
    for (const l of cart.items || []) if (covered.has(l.sku)) await api.removeItem(cart._id, l.lineId);
    await api.addItem(cart._id, { productId: combo.productId, qty: 1 });
    await refreshCart();
  };
  const changeQty = async (line, delta) => {
    const next = line.qty + delta;
    if (next <= 0) await api.removeItem(cart._id, line.lineId);
    else await api.setItemQty(cart._id, line.lineId, next);
    await refreshCart();
  };
  const remove = async (lineId) => { await api.removeItem(cart._id, lineId); await refreshCart(); };
  const applyVoucher = async () => {
    const res = await api.applyVoucher(cart._id, code);
    setVoucherMsg(res.applied ? `Đã áp dụng −${vnd(res.discount)}` : "Mã không hợp lệ");
    await refreshCart();
  };

  const empty = !cart?.items?.length;
  const count = cart?.items?.reduce((s, l) => s + l.qty, 0) || 0;

  const DineToggle = () => (
    <div className="flex items-center gap-2 text-sm">
      <button onClick={() => setDineMode("dine_in")}
        className={`px-2 py-1 rounded-full border ${dineMode === "dine_in" ? "border-kfcred text-kfcred font-semibold" : "border-gray-200 text-gray-400"}`}>🍽️ {t("dineIn")}</button>
      <button onClick={() => setDineMode("takeaway")}
        className={`px-2 py-1 rounded-full border ${dineMode === "takeaway" ? "border-kfcred text-kfcred font-semibold" : "border-gray-200 text-gray-400"}`}>🥡 {t("takeaway")}</button>
    </div>
  );

  return (
    <div className="flex-1 flex flex-col pb-44 bg-white">
      {/* Header */}
      <div className="px-4 py-3 flex items-center justify-between">
        <button onClick={onBack} className="flex items-center gap-2">
          <span className="text-gray-400">←</span>
          <h2 className="font-black text-lg text-kfcdark">{t("myOrder")}</h2>
          <span className="bg-gray-100 text-gray-600 text-xs rounded px-1.5 py-0.5">{count}</span>
        </button>
        <DineToggle />
      </div>

      {empty ? (
        <div className="flex-1 flex flex-col items-center justify-center text-gray-400 gap-4">
          <div className="text-6xl">🪣</div>
          <div className="text-gray-500">{t("emptyCart")}</div>
          <button onClick={onBack} className="bg-kfcred text-white rounded-full px-8 py-2.5 font-semibold">{t("addMore")}</button>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto">
          <div className="px-4 divide-y divide-gray-100">
            {cart.items.map((l) => (
              <div key={l.lineId} className="py-3 flex items-center gap-3">
                <div className="w-14 h-14 bg-gray-50 rounded-lg overflow-hidden shrink-0 flex items-center justify-center text-2xl">
                  {l.imageUrl ? <img src={l.imageUrl} alt={l.name_vi} className="w-full h-full object-cover" /> : "🍗"}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-sm truncate">{l.name_vi}</div>
                  <div className="text-kfcred font-bold text-sm">{vnd(l.lineTotal)}</div>
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={() => changeQty(l, -1)} className="w-7 h-7 rounded-full border border-gray-300 text-gray-600">−</button>
                  <span className="w-5 text-center text-sm font-semibold">{l.qty}</span>
                  <button onClick={() => changeQty(l, +1)} className="w-7 h-7 rounded-full border border-kfcred text-kfcred">+</button>
                </div>
              </div>
            ))}
          </div>
          <RecoStrip slot="cart" context={recoContext()} title={t("completeMeal") || "Hoàn thiện bữa ăn"} t={t} onAdd={addReco} onUpgrade={upgrade} limit={3} />
        </div>
      )}

      {/* Bottom stack */}
      <div className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[480px] bg-white">
        {!user && (
          <div className="bg-kfcred text-white px-4 py-2.5 flex items-center justify-between">
            <span className="text-xs font-semibold pr-2">{t("memberBanner")}</span>
            <button onClick={openLogin} className="bg-white text-kfcred rounded-md px-3 py-1 text-xs font-bold whitespace-nowrap">{t("loginBtn")}</button>
          </div>
        )}
        <div className="px-4 py-2 border-t border-gray-100 flex items-center gap-3">
          <button onClick={() => setShowCode((v) => !v)} className="flex-1 border border-gray-200 rounded-lg py-2 text-xs font-semibold text-kfcred flex items-center justify-center gap-1">🏷️ {t("choosePromo")}</button>
          <button onClick={() => setShowCode((v) => !v)} className="flex-1 border border-gray-200 rounded-lg py-2 text-xs font-semibold text-kfcred flex items-center justify-center gap-1">▥ {t("voucher")}</button>
          <div className="text-right text-xs">
            <div className="text-gray-500">{t("subtotal")}: <b className="text-kfcdark">{vnd(cart?.totals?.subtotal)}</b></div>
            <div className="text-gray-500">{t("discountLbl")}: <b className="text-kfcred">−{vnd(cart?.totals?.discount)}</b></div>
          </div>
        </div>
        {showCode && (
          <div className="px-4 pb-2 flex gap-2">
            <input value={code} onChange={(e) => setCode(e.target.value)} placeholder={t("voucher")}
              className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm" />
            <button onClick={applyVoucher} className="bg-kfcred text-white rounded-lg px-4 text-sm font-semibold">{t("apply")}</button>
          </div>
        )}
        {voucherMsg && <div className="px-4 pb-1 text-xs text-kfcred">{voucherMsg}</div>}
        <div className="px-4 py-2.5 border-t border-gray-200 flex items-center gap-2">
          <div className="w-10 h-10 rounded-full border border-gray-200 flex items-center justify-center text-gray-400">♿</div>
          <button onClick={onBack} className="flex-1 border border-gray-300 rounded-full py-2.5 text-sm font-semibold text-gray-600">{t("addMore")}</button>
          <button onClick={onCheckout} disabled={empty}
            className="flex-[1.3] bg-kfcred text-white rounded-full py-2.5 font-bold text-sm disabled:opacity-40">
            {t("checkout")} · {vnd(cart?.totals?.grandTotal)}
          </button>
        </div>
      </div>
    </div>
  );
}
