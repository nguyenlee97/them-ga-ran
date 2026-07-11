import { Router } from "express";
import Product from "../models/Product.js";
import Store from "../models/Store.js";
import User from "../models/User.js";
import Transaction from "../models/Transaction.js";
import AssocRule from "../models/AssocRule.js";
import Order from "../models/Order.js";
import Event from "../models/Event.js";
import { asyncH } from "../middleware/error.js";
import { DASHBOARD_HTML } from "./metricsDashboard.js";

const r = Router();

// Quick inspection endpoints for demo/debugging.
r.get("/stats", asyncH(async (req, res) => {
  const [products, stores, users, transactions, rules, orders] = await Promise.all([
    Product.countDocuments(), Store.countDocuments(), User.countDocuments(),
    Transaction.countDocuments(), AssocRule.countDocuments(), Order.countDocuments(),
  ]);
  res.json({ products, stores, users, transactions, assocRules: rules, orders });
}));

r.get("/rules", asyncH(async (req, res) => {
  const rules = await AssocRule.find().sort({ lift: -1 }).limit(Number(req.query.limit) || 50).lean();
  res.json({ count: rules.length, rules });
}));

/**
 * GET /api/admin/metrics?days=N — the AOV-uplift evidence.
 * Funnel (shown→accepted) by slot & strategy, revenue directly attributable
 * to accepted recommendations, combo trade-up performance, and AOV of orders
 * WITH vs WITHOUT an accepted recommendation on the cart.
 */
r.get("/metrics", asyncH(async (req, res) => {
  const days = Number(req.query.days) || 0;
  const since = days ? new Date(Date.now() - days * 864e5) : null;
  const evMatch = since ? { ts: { $gte: since } } : {};
  const orderMatch = since ? { placedAt: { $gte: since } } : {};

  const [shownAgg, acceptedBySlot, acceptedByStrategy, acceptedEvents, comboShown, comboAccepted, orders] =
    await Promise.all([
      Event.aggregate([
        { $match: { ...evMatch, type: "reco_shown" } },
        { $project: { slot: 1, n: { $size: { $ifNull: ["$payload.items", []] } } } },
        { $group: { _id: "$slot", responses: { $sum: 1 }, itemImpressions: { $sum: "$n" } } },
      ]),
      Event.aggregate([
        { $match: { ...evMatch, type: "reco_accepted" } },
        { $group: { _id: "$slot", n: { $sum: 1 } } },
      ]),
      Event.aggregate([
        { $match: { ...evMatch, type: "reco_accepted" } },
        { $group: { _id: "$strategy", n: { $sum: 1 } } },
      ]),
      Event.find({ ...evMatch, type: "reco_accepted" }, { productId: 1, cartId: 1 }).lean(),
      Event.countDocuments({ ...evMatch, type: "reco_shown", "payload.combo": { $nin: [null, ""] } }),
      Event.find({ ...evMatch, type: "combo_upgrade_accepted" }, { cartId: 1, payload: 1 }).lean(),
      Order.find(orderMatch, { cartId: 1, totals: 1 }).lean(),
    ]);

  // Revenue directly attributable to accepted recommendation items.
  const skus = [...new Set(acceptedEvents.map((e) => e.productId).filter(Boolean))];
  const prods = skus.length
    ? await Product.find({ sku: { $in: skus } }, { sku: 1, price: 1 }).lean()
    : [];
  const priceOf = Object.fromEntries(prods.map((p) => [p.sku, p.price || 0]));
  const acceptedRecRevenue = acceptedEvents.reduce((s, e) => s + (priceOf[e.productId] || 0), 0);

  // AOV: orders whose cart had ≥1 accepted rec (or combo trade-up) vs the rest.
  const recCarts = new Set(
    [...acceptedEvents, ...comboAccepted].map((e) => String(e.cartId || "")).filter(Boolean)
  );
  const withRec = { orders: 0, revenue: 0 };
  const withoutRec = { orders: 0, revenue: 0 };
  for (const o of orders) {
    const b = recCarts.has(String(o.cartId || "")) ? withRec : withoutRec;
    b.orders += 1;
    b.revenue += o.totals?.grandTotal || 0;
  }
  const aovWith = withRec.orders ? withRec.revenue / withRec.orders : 0;
  const aovWithout = withoutRec.orders ? withoutRec.revenue / withoutRec.orders : 0;

  const itemImpressions = shownAgg.reduce((s, x) => s + x.itemImpressions, 0);
  const acceptedN = acceptedEvents.length;
  const slotIds = [...new Set([...shownAgg.map((x) => x._id), ...acceptedBySlot.map((x) => x._id)])];

  res.json({
    windowDays: days || "all",
    funnel: {
      responses: shownAgg.reduce((s, x) => s + x.responses, 0),
      itemImpressions,
      accepted: acceptedN,
      acceptanceRate: itemImpressions ? acceptedN / itemImpressions : 0,
    },
    bySlot: slotIds.map((slot) => {
      const s = shownAgg.find((x) => x._id === slot);
      const a = acceptedBySlot.find((x) => x._id === slot);
      const shown = s?.itemImpressions || 0;
      return { slot: slot || "?", shown, accepted: a?.n || 0, rate: shown ? (a?.n || 0) / shown : null };
    }),
    byStrategy: acceptedByStrategy.map((x) => ({ strategy: x._id || "?", accepted: x.n })),
    comboUpsell: { shown: comboShown, accepted: comboAccepted.length,
      rate: comboShown ? comboAccepted.length / comboShown : 0 },
    revenue: { acceptedRecRevenue },
    aov: {
      withRec: { orders: withRec.orders, aov: Math.round(aovWith) },
      withoutRec: { orders: withoutRec.orders, aov: Math.round(aovWithout) },
      upliftPct: withRec.orders && withoutRec.orders && aovWithout
        ? ((aovWith - aovWithout) / aovWithout) * 100
        : null,
    },
  });
}));

// Human-readable dashboard over /metrics — open http://localhost:3000/api/admin/dashboard
r.get("/dashboard", (req, res) => res.type("html").send(DASHBOARD_HTML));

export default r;
