import { useState } from "react";

/**
 * Login modal — overlay over the current screen (matches the real kiosk's
 * ĐĂNG NHẬP popup). Scan-member illustration + phone/code fallback + Bỏ qua/Xác nhận.
 */
export default function LoginModal({ t, lang, setLang, onConfirm, onSkip, onClose }) {
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const confirm = async () => {
    if (!phone) { setErr("Vui lòng nhập số điện thoại."); return; }
    setBusy(true); setErr("");
    try { await onConfirm(phone, code); }
    catch { setErr("Đăng nhập thất bại. Thử lại nhé."); setBusy(false); }
  };

  return (
    <div className="absolute inset-0 z-40 bg-black/50 flex items-center justify-center p-3">
      <div className="w-full max-h-full overflow-y-auto bg-white rounded-2xl border-2 border-kfcred/70 flex flex-col">
        {/* KFC mark */}
        <div className="pt-5 flex justify-center">
          <div className="flex gap-[3px]">
            <span className="w-2 h-6 bg-kfcred/80 rounded-sm" />
            <span className="w-2 h-6 bg-kfcred rounded-sm" />
            <span className="w-2 h-6 bg-kfcred/80 rounded-sm" />
          </div>
        </div>

        <h1 className="text-center text-2xl font-black text-kfcdark mt-3">ĐĂNG NHẬP</h1>
        <p className="text-center text-sm text-gray-600 px-8 mt-3 leading-snug">
          Vui lòng quét mã thành viên trong app KFC, đầu đọc mã ở cạnh dưới màn hình Kiosk
        </p>

        {/* scanner illustration */}
        <div className="my-4 flex justify-center">
          <div className="w-20 h-28 border-2 border-gray-300 rounded-lg flex items-center justify-center relative">
            <span className="w-5 h-5 rounded-full border-2 border-green-500 animate-pulse" />
            <span className="absolute -bottom-3 w-10 h-8 border-2 border-gray-300 rounded" />
          </div>
        </div>
        <p className="text-center text-xs text-gray-500 px-10">
          Hướng mã khuyến mãi về phía đầu đọc và giữ khoảng cách xa khoảng <b>20 cm</b> bạn nhé.
        </p>

        <div className="text-center text-kfcred font-bold text-sm mt-4">HOẶC</div>
        <p className="text-center text-sm font-semibold text-kfcdark">Đăng nhập bằng số điện thoại</p>

        <div className="px-8 mt-3">
          <input value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel"
            placeholder="Số điện thoại *"
            className="w-full border-b-2 border-gray-200 py-2 mb-4 outline-none focus:border-kfcred text-sm" />
          <input value={code} onChange={(e) => setCode(e.target.value)}
            placeholder="Mã (không bắt buộc)"
            className="w-full border-b-2 border-gray-200 py-2 outline-none focus:border-kfcred text-sm" />
          <p className="text-xs text-gray-400 mt-4 text-center">
            Để sử dụng các mã dành riêng cho bạn, bạn sẽ cần đăng nhập
          </p>
          {err && <div className="text-sm text-kfcred text-center mt-2">{err}</div>}
        </div>

        <div className="flex gap-3 px-8 mt-4 mb-3">
          <button onClick={onSkip} className="flex-1 border border-gray-300 rounded-lg py-3 font-semibold text-kfcdark">
            Bỏ qua
          </button>
          <button onClick={confirm} disabled={busy}
            className="flex-1 bg-kfcred text-white rounded-lg py-3 font-semibold disabled:opacity-50">
            {busy ? "…" : "Xác nhận"}
          </button>
        </div>

        <div className="flex border-t border-gray-200 text-sm">
          {[["vi", "Tiếng Việt"], ["en", "English"]].map(([l, label]) => (
            <button key={l} onClick={() => setLang(l)}
              className={`flex-1 py-3 ${lang === l ? "font-bold text-kfcred" : "text-gray-500"}`}>
              {label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
