import { useState } from "react";

export default function Login({ t, onLogin, onSkip }) {
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    if (!phone) { setErr("Vui lòng nhập số điện thoại."); return; }
    setBusy(true); setErr("");
    try {
      await onLogin(phone, code);
    } catch (e) {
      setErr("Đăng nhập thất bại. Thử lại nhé.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col px-5 py-6">
      <h1 className="text-2xl font-black text-center text-kfcdark">{t("login")}</h1>
      <p className="text-center text-sm text-gray-500 mt-2">
        Quét mã thành viên trong app KFC, hoặc đăng nhập bằng số điện thoại
      </p>

      <div className="my-6 mx-auto w-40 h-40 border-2 border-dashed border-gray-300 rounded-2xl flex items-center justify-center text-gray-300">
        <div className="text-center">
          <div className="text-5xl">▣</div>
          <div className="text-xs mt-1">QR</div>
        </div>
      </div>

      <div className="text-center text-kfcred font-bold text-sm">HOẶC</div>
      <p className="text-center text-sm font-semibold mb-3">{t("loginPrompt")}</p>

      <input
        value={phone} onChange={(e) => setPhone(e.target.value)}
        placeholder={t("phone") + " *"} inputMode="tel"
        className="border-b-2 border-gray-200 py-2 mb-3 outline-none focus:border-kfcred"
      />
      <input
        value={code} onChange={(e) => setCode(e.target.value)}
        placeholder={t("code") + " (không bắt buộc)"}
        className="border-b-2 border-gray-200 py-2 mb-2 outline-none focus:border-kfcred"
      />
      <p className="text-xs text-gray-400 mb-4">
        Để sử dụng ưu đãi & tích điểm dành riêng cho bạn, bạn cần đăng nhập.
      </p>
      {err && <div className="text-sm text-kfcred mb-3">{err}</div>}

      <div className="flex gap-3 mt-auto">
        <button onClick={onSkip} className="flex-1 border border-gray-300 rounded-xl py-3 font-semibold">
          {t("skip")}
        </button>
        <button onClick={submit} disabled={busy}
          className="flex-1 bg-kfcred text-white rounded-xl py-3 font-semibold disabled:opacity-50">
          {busy ? "…" : t("confirm")}
        </button>
      </div>
    </div>
  );
}
