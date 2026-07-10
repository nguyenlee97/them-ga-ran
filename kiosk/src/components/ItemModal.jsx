import RecoStrip from "./RecoStrip.jsx";

/**
 * Shown right after a customer adds an item — the highest-converting upsell
 * moment. Surfaces slot="item_added" recommendations ("goes great with").
 */
export default function ItemModal({ t, addedName, context, onAdd, onUpgrade, onContinue, onViewCart }) {
  return (
    <div className="fixed inset-0 z-30 bg-black/40 flex items-end justify-center">
      <div className="w-full max-w-[480px] bg-white rounded-t-2xl p-4 animate-[slideUp_.2s_ease-out]">
        <div className="text-center mb-2">
          <div className="text-green-600 text-2xl">✓</div>
          <div className="font-semibold">{addedName}</div>
        </div>

        <RecoStrip slot="item_added" context={context} title={t("goesWellWith")} t={t} onAdd={onAdd} onUpgrade={onUpgrade} limit={3} />

        <div className="flex gap-2 mt-3">
          <button onClick={onContinue} className="flex-1 border border-gray-300 rounded-xl py-3 font-semibold">
            {t("addMore")}
          </button>
          <button onClick={onViewCart} className="flex-1 bg-kfcred text-white rounded-xl py-3 font-semibold">
            {t("viewCart")}
          </button>
        </div>
      </div>
    </div>
  );
}
