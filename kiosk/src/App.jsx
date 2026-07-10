import { useEffect, useState, useCallback } from "react";
import { api } from "./lib/api.js";
import { makeT } from "./i18n/index.js";
import { timeOfDay, dayOfWeek } from "./lib/format.js";
import Attract from "./screens/Attract.jsx";
import Menu from "./screens/Menu.jsx";
import Cart from "./screens/Cart.jsx";
import Checkout from "./screens/Checkout.jsx";
import LoginModal from "./components/LoginModal.jsx";

export default function App() {
  const [lang, setLang] = useState("vi");
  const [screen, setScreen] = useState("attract");
  const [dineMode, setDineMode] = useState("dine_in");
  const [storeId, setStoreId] = useState(null);
  const [user, setUser] = useState(null);
  const [loyalty, setLoyalty] = useState(null);
  const [cart, setCart] = useState(null);
  const [order, setOrder] = useState(null);
  const [showLogin, setShowLogin] = useState(false);

  const t = makeT(lang);

  useEffect(() => {
    fetch((import.meta.env.VITE_API_URL || "") + "/api/stores")
      .then((r) => r.json())
      .then((d) => setStoreId(d.stores?.[0]?._id || null))
      .catch(() => {});
  }, []);

  const ensureCart = useCallback(async (u = user, mode = dineMode) => {
    if (cart?._id) {
      if (u && !cart.userId) { const c = await api.patchCart(cart._id, { userId: u.id }); setCart(c); return c; }
      return cart;
    }
    const c = await api.createCart({ channel: "kiosk", storeId, dineMode: mode, userId: u?.id || null });
    setCart(c);
    return c;
  }, [cart, user, dineMode, storeId]);

  const refreshCart = useCallback(async () => {
    if (cart?._id) setCart(await api.getCart(cart._id));
  }, [cart]);

  const doLogin = async (phone, code) => {
    const res = await api.login(phone, code);
    setUser(res.user); setLoyalty(res.loyalty);
    await ensureCart(res.user);
    return res;
  };

  // From attract: pick dine mode → open login modal.
  const startOrder = (mode) => { setDineMode(mode); setShowLogin(true); };

  const recoContext = useCallback(() => ({
    cartId: cart?._id, storeId, dineMode, channel: "kiosk",
    timeOfDay: timeOfDay(), dayOfWeek: dayOfWeek(), userId: user?.id || null,
  }), [cart, storeId, dineMode, user]);

  const resetAll = () => {
    setOrder(null); setCart(null); setUser(null); setLoyalty(null);
    setDineMode("dine_in"); setScreen("attract");
  };

  const shared = { t, lang, setLang, dineMode, setDineMode, user, loyalty, cart,
    setCart, refreshCart, recoContext, storeId, openLogin: () => setShowLogin(true) };

  return (
    <div className="mx-auto max-w-[480px] min-h-screen bg-white shadow-xl flex flex-col relative overflow-hidden">
      {screen === "attract" && <Attract {...shared} onStart={startOrder} />}
      {screen === "menu" && <Menu {...shared} onViewCart={() => setScreen("cart")} onHome={resetAll} />}
      {screen === "cart" && (
        <Cart {...shared} onBack={() => setScreen("menu")} onCheckout={() => setScreen("checkout")} />
      )}
      {screen === "checkout" && (
        <Checkout {...shared} order={order} onPaid={(o) => setOrder(o)} onNewOrder={resetAll}
          onBack={() => setScreen("cart")} />
      )}

      {showLogin && (
        <LoginModal
          t={t} lang={lang} setLang={setLang}
          onConfirm={async (phone, code) => {
            await doLogin(phone, code);
            setShowLogin(false);
            if (screen === "attract") setScreen("menu");
          }}
          onSkip={async () => {
            if (screen === "attract") { await ensureCart(null); setScreen("menu"); }
            setShowLogin(false);
          }}
          onClose={() => setShowLogin(false)}
        />
      )}
    </div>
  );
}
