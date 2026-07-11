import { useState } from "react";
import { api } from "../lib/api.js";
import { vnd, uuid } from "../lib/format.js";
import RecoStrip from "../components/RecoStrip.jsx";

export default function Checkout(props) {
  const { t, cart, refreshCart, recoContext, order, onPaid, onNewOrder, onBack } = props;
  const [busy, setBusy] = useState(false);
  const [idemKey] = useState(uuid());

  const addReco = async (productId) => { await api.addItem(cart._id, { productId, qty: 1 }); await refreshCart(); };
  const upgrade = async (combo) => {
    const covered = new Set(combo.covers || []);
    for (const l of cart.items || []) if (covered.has(l.sku)) await api.removeItem(cart._id, l.lineId);
    await api.addItem(cart._id, { productId: combo.productId, qty: 1 });
    await refreshCart();
  };
  const pay = async () => {
    setBusy(true);
    try {
      const res = await api.placeOrder({ cartId: cart._id, idempotencyKey: idemKey, payment: { method: "mock" } });
      onPaid(res.order ? { ...res.order, pointsEarned: res.pointsEarned } : res);
    } finally { setBusy(false); }
  };

  if (order) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center px-6 text-center gap-3 bg-white">
        <div className="text-6xl">✅</div>
        <h2 className="text-2xl font-black text-kfcdark">{t("orderConfirmed") || "Đặt hàng thành công!"}</h2>
        <div className="text-gray-500">Mã đơn: {String(order._id || "").slice(-6).toUpperCase()}</div>
        <div className="text-3xl font-black text-kfcred">{vnd(order.totals?.grandTotal)}</div>
        {order.pointsEarned > 0 && (
          <div className="bg-kfcred/10 text-kfcred rounded-xl px-4 py-2 font-semibold">
            +{order.pointsEarned} {t("pointsEarned") || "điểm tích luỹ"} 🎉
          </div>
        )}
        <button onClick={onNewOrder} className="mt-4 bg-kfcred text-white rounded-full px-8 py-3 font-bold">
          {t("newOrder") || "Đơn mới"}
        </button>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col pb-28 bg-white">
      <div className="px-4 py-3 flex items-center gap-2">
        <button onClick={onBack} className="text-gray-400">←</button>
        <h2 className="font-black text-lg text-kfcdark">{t("checkout")}</h2>
      </div>

      <RecoStrip slot="checkout" context={{ ...recoContext(), cartVersion: `${cart?.items?.length || 0}-${cart?.totals?.grandTotal}` }} title={t("beforePay") || "Thêm chút nữa nhé?"} t={t} onAdd={addReco} onUpgrade={upgrade} limit={3} />

      <div className="px-4 mt-2">
        {/* itemized order summary */}
        <div className="border border-gray-200 rounded-xl divide-y divide-gray-100 mb-3">
          {(cart?.items || []).map((l) => (
            <div key={l.lineId} className="flex items-center gap-3 p-2.5">
              <div className="w-10 h-10 bg-gray-50 rounded-md overflow-hidden shrink-0 flex items-center justify-center text-lg">
                {l.imageUrl ? <img src={l.imageUrl} alt={l.name_vi} className="w-full h-full object-cover" /> : "🍗"}
              </div>
              <div className="flex-1 min-w-0 text-sm">
                <div className="font-medium truncate">{l.name_vi}</div>
                <div className="text-xs text-gray-400">x{l.qty}</div>
              </div>
              <div className="text-sm font-semibold text-kfcdark">{vnd(l.lineTotal)}</div>
            </div>
          ))}
        </div>
        <div className="border border-gray-200 rounded-xl p-4 space-y-1">
          <div className="flex justify-between text-sm text-gray-500"><span>{t("subtotal")}</span><span>{vnd(cart?.totals?.subtotal)}</span></div>
          {cart?.totals?.discount > 0 && (
            <div className="flex justify-between text-sm text-kfcred"><span>{t("discountLbl")}</span><span>−{vnd(cart.totals.discount)}</span></div>
          )}
          <div className="flex justify-between font-black text-lg pt-1"><span>{t("total")}</span><span className="text-kfcred">{vnd(cart?.totals?.grandTotal)}</span></div>
        </div>
        <div className="text-xs text-gray-400 mt-2">Thanh toán giả lập (demo) — không tính phí thật.</div>
      </div>

      <div className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[480px] bg-white border-t border-gray-200 px-4 py-3">
        <button onClick={pay} disabled={busy || !cart?.items?.length}
          className="w-full bg-kfcred text-white rounded-full py-4 font-bold text-lg disabled:opacity-50">
          {busy ? "…" : `${t("checkout")} · ${vnd(cart?.totals?.grandTotal)}`}
        </button>
      </div>
    </div>
  );
}
