import { useState } from "react";
import { api } from "../lib/api.js";
import { vnd, uuid } from "../lib/format.js";
import Header from "../components/Header.jsx";
import RecoStrip from "../components/RecoStrip.jsx";

export default function Checkout(props) {
  const { t, cart, refreshCart, recoContext, order, onPaid, onNewOrder } = props;
  const [busy, setBusy] = useState(false);
  const [idemKey] = useState(uuid()); // stable across retries of THIS checkout

  const addReco = async (productId) => {
    await api.addItem(cart._id, { productId, qty: 1 });
    await refreshCart();
  };

  const pay = async () => {
    setBusy(true);
    try {
      const res = await api.placeOrder({ cartId: cart._id, idempotencyKey: idemKey, payment: { method: "mock" } });
      onPaid(res.order ? { ...res.order, pointsEarned: res.pointsEarned } : res);
    } finally {
      setBusy(false);
    }
  };

  // Confirmation view
  if (order) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center px-6 text-center gap-3">
        <div className="text-6xl">✅</div>
        <h2 className="text-2xl font-black text-kfcdark">{t("orderConfirmed")}</h2>
        <div className="text-gray-500">Mã đơn: {String(order._id || "").slice(-6).toUpperCase()}</div>
        <div className="text-3xl font-black text-kfcred">{vnd(order.totals?.grandTotal)}</div>
        {order.pointsEarned > 0 && (
          <div className="bg-kfcred/10 text-kfcred rounded-xl px-4 py-2 font-semibold">
            +{order.pointsEarned} {t("pointsEarned")} 🎉
          </div>
        )}
        <button onClick={onNewOrder} className="mt-4 bg-kfcred text-white rounded-xl px-8 py-3 font-bold">
          {t("newOrder")}
        </button>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col pb-32">
      <Header {...props} />
      <div className="px-4 py-3">
        <h2 className="font-black text-lg">{t("checkout")}</h2>
      </div>

      {/* One last low-friction upsell before payment */}
      <RecoStrip slot="checkout" context={recoContext()} title={t("beforePay")} t={t} onAdd={addReco} limit={3} />

      <div className="px-4 mt-2">
        <div className="border border-gray-200 rounded-xl p-4">
          <div className="flex justify-between text-sm text-gray-500">
            <span>Tạm tính</span><span>{vnd(cart?.totals?.subtotal)}</span>
          </div>
          {cart?.totals?.discount > 0 && (
            <div className="flex justify-between text-sm text-kfcred">
              <span>Khuyến mãi</span><span>−{vnd(cart.totals.discount)}</span>
            </div>
          )}
          <div className="flex justify-between font-black text-lg mt-1">
            <span>{t("total")}</span><span className="text-kfcred">{vnd(cart?.totals?.grandTotal)}</span>
          </div>
        </div>
        <div className="text-xs text-gray-400 mt-2">Thanh toán giả lập (demo) — không tính phí thật.</div>
      </div>

      <div className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[480px] bg-white border-t border-gray-200 px-4 py-3">
        <button onClick={pay} disabled={busy || !cart?.items?.length}
          className="w-full bg-kfcred text-white rounded-xl py-4 font-bold text-lg disabled:opacity-50">
          {busy ? "…" : `${t("checkout")} · ${vnd(cart?.totals?.grandTotal)}`}
        </button>
      </div>
    </div>
  );
}
