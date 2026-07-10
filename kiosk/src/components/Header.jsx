export default function Header({ t, lang, setLang, dineMode, user, loyalty }) {
  return (
    <div className="sticky top-0 z-10 bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <div className="bg-kfcred text-white font-black px-2 py-1 rounded text-lg tracking-tight">KFC</div>
        <span className="text-xs text-gray-500">
          {dineMode === "dine_in" ? t("dineIn") : t("takeaway")}
        </span>
      </div>
      <div className="flex items-center gap-3">
        {user && (
          <div className="text-right leading-tight">
            <div className="text-xs text-gray-500">{t("welcomeBack")}</div>
            <div className="text-sm font-semibold">
              {user.name} · {loyalty?.pointsBalance ?? 0} {t("points")}
            </div>
          </div>
        )}
        <div className="flex rounded-full border border-gray-300 overflow-hidden text-xs">
          {["vi", "en"].map((l) => (
            <button
              key={l}
              onClick={() => setLang(l)}
              className={`px-2 py-1 ${lang === l ? "bg-kfcred text-white" : "bg-white text-gray-600"}`}
            >
              {l.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
