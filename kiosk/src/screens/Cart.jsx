import { useState } from "react";
import { api } from "../lib/api.js";
import { vnd } from "../lib/format.js";
import Header from "../components/Header.jsx";
import RecoStrip from "../components/RecoStrip.jsx";

export default function Cart(props) {
  const { t, cart, refreshCart, recoContext, onBack, onCheckout } = props;
  const [code, setCode] = useState("");
  const [voucherMsg, setVoucherMsg] = useState("");

  const addReco = async (productId) => {
    await api.addItem(cart._id, { productId, qty: 1 });
    await refreshCart();
  };
  const remove = async (lineId) => {
    await api.removeItem(cart._id, lineId);
    await refreshCart();
  };
  const applyVoucher = async () => {
    const res = await api.applyVoucher(cart._id, code);
    setVoucherMsg(res.applied ? `−${vnd(res.discount)}` : "Mã không hợp lệ");
    await refreshCart();
  };

  const empty = !cart?.items?.length;

  return (
    <div className="flex-1 flex flex-col pb-40">
      <Header {...props} />
      <div className="px-4 py-3 flex items-center gap-2">
        <button onClick={onBack} className="text-gray-500">←</button>
        <h2 className="font-black text-lg">🛒 {t("viewCart")}</h2>
      </div>

      {empty ? (
        <div className="flex-1 flex flex-col items-center justify-center text-gray-400 gap-3">
          <div className="text-5xl">🪣</div>
          <div>{t("emptyCart")}</div>
          <button onClick={onBack} className="bg-kfcred text-white rounded-full px-6 py-2 font-semibold">
            {t("addMore")}
          </button>
        </div>
      ) : (
        <>
          <div className="px-4 divide-y divide-gray-100">
            {cart.items.map((l) => (
              <div key={l.lineId} className="py-3 flex items-center gap-3">
                <div className="w-12 h-12 bg-gray-100 rounded-lg flex items-center justify-center text-2xl">🍗</div>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-sm truncate">{l.name_vi}</div>
                  <div className="text-xs text-gray-500">x{l.qty} · {vnd(l.unitPrice)}</div>
                </div>
                <div className="text-sm font-bold">{vnd(l.lineTotal)}</div>
                <button onClick={() => remove(l.lineId)} className="text-gray-400 text-xs">✕</button>
              </div>
            ))}
          </div>

          {/* Complete-the-meal reco */}
          <RecoStrip slot="cart" context={recoContext()} title={t("completeMeal")} t={t} onAdd={addReco} limit={3} />

          {/* Voucher */}
          <div className="px-4 py-3 flex gap-2">
            <input value={code} onChange={(e) => setCode(e.target.value)}
              placeholder={t("voucher")} className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm" />
            <button onClick={applyVoucher} className="border border-kfcred text-kfcred rounded-lg px-4 font-semibold text-sm">
              {t("apply")}
            </button>
          </div>
          {voucherMsg && <div className="px-4 text-sm text-kfcred">{voucherMsg}</div>}
        </>
      )}

      {/* Footer totals */}
      {!empty && (
        <div className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[480px] bg-white border-t border-gray-200 px-4 py-3">
          <div className="flex justify-between text-sm text-gray-500">
            <span>Tạm tính</span><span>{vnd(cart.totals.subtotal)}</span>
          </div>
          {cart.totals.discount > 0 && (
            <div className="flex justify-between text-sm text-kfcred">
              <span>Khuyến mãi</span><span>−{vnd(cart.totals.discount)}</span>
            </div>
          )}
          <div className="flex justify-between font-black text-lg mt-1">
            <span>{t("total")}</span><span className="text-kfcred">{vnd(cart.totals.grandTotal)}</span>
          </div>
          <button onClick={onCheckout} className="w-full bg-kfcred text-white rounded-xl py-3 font-bold mt-2">
            {t("checkout")}
          </button>
        </div>
      )}
    </div>
  );
}
