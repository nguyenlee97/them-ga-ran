import { useState } from "react";

export default function Attract({ lang, setLang, onStart }) {
  const [imgOk, setImgOk] = useState(true);

  return (
    <div className="flex-1 flex flex-col bg-white">
      {/* Red header */}
      <div className="bg-white pt-5 px-5 text-center">
        <div className="flex items-center justify-center gap-3">
          <div className="bg-kfcred text-white font-black px-2 py-3 rounded leading-none text-sm">KFC</div>
          <h1 className="text-4xl font-black text-kfcdark tracking-tight">ĐẶT HÀNG TẠI ĐÂY</h1>
        </div>
      </div>

      {/* Promo hero — drop real graphic at /assets/welcome-hero.png (1080×1400). */}
      <div className="flex-1 px-4 py-4">
        {imgOk ? (
          <img src="/assets/welcome-hero.png" alt="KFC Rewards"
            onError={() => setImgOk(false)}
            className="w-full h-full object-contain rounded-xl" />
        ) : (
          <PromoFallback />
        )}
      </div>

      {/* Dine-mode = entry action */}
      <div className="px-5 pb-3">
        <div className="grid grid-cols-2 gap-3">
          <button onClick={() => onStart("dine_in")}
            className="rounded-2xl border-2 border-gray-200 py-5 flex flex-col items-center gap-2 active:border-kfcred active:bg-kfcred/5">
            <span className="text-3xl">🍽️</span>
            <span className="font-bold text-kfcdark">ĂN TẠI CHỖ</span>
          </button>
          <button onClick={() => onStart("takeaway")}
            className="rounded-2xl border-2 border-gray-200 py-5 flex flex-col items-center gap-2 active:border-kfcred active:bg-kfcred/5">
            <span className="text-3xl">🥡</span>
            <span className="font-bold text-kfcdark">MUA MANG VỀ</span>
          </button>
        </div>
      </div>

      {/* Language */}
      <div className="grid grid-cols-2 gap-3 px-5 pb-5">
        {[["vi", "Tiếng Việt"], ["en", "English"]].map(([l, label]) => (
          <button key={l} onClick={() => setLang(l)}
            className={`rounded-full border py-2 text-sm ${lang === l ? "border-kfcred text-kfcred font-semibold" : "border-gray-300 text-gray-500"}`}>
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}

/** CSS fallback resembling the KFC Rewards promo so the screen looks right
 *  before the real hero image is dropped in. */
function PromoFallback() {
  return (
    <div className="w-full h-full rounded-xl bg-gradient-to-b from-white to-gray-50 border border-gray-100 flex flex-col items-center justify-center text-center px-6 py-6">
      <div className="text-xs font-black text-kfcred tracking-widest">KFC REWARDS</div>
      <h2 className="text-2xl font-black text-kfcred mt-2">ĐĂNG KÝ THÀNH VIÊN</h2>
      <p className="text-lg font-bold text-kfcdark">MỞ KHÓA ƯU ĐÃI</p>
      <div className="my-5 flex items-center justify-center gap-3">
        {[["3%", "Thành Viên"], ["5%", "Vàng"], ["7%", "Bạch Kim"]].map(([p, l]) => (
          <div key={p} className="bg-kfcred text-white rounded-2xl px-4 py-3">
            <div className="text-3xl font-black">{p}</div>
            <div className="text-[10px] uppercase">{l}</div>
          </div>
        ))}
      </div>
      <div className="mt-2 bg-kfcred/10 text-kfcred rounded-xl px-5 py-3 font-bold">
        Deal Chào Bạn Mới · 1 Miếng Gà + 1 Pepsi — <span className="text-2xl">25K</span>
      </div>
      <p className="text-[11px] text-gray-400 mt-4">(Đặt ảnh quảng cáo tại /assets/welcome-hero.png)</p>
    </div>
  );
}
