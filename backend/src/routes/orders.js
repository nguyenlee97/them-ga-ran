import { Router } from "express";
import Order from "../models/Order.js";
import Event from "../models/Event.js";
import Transaction from "../models/Transaction.js";
import Product from "../models/Product.js";
import { placeOrder } from "../services/orderService.js";
import { asyncH, httpError } from "../middleware/error.js";

const r = Router();

// GET /api/orders/user/:userId?limit=5 — member's recent orders (chat: "đơn của tôi")
// Declared BEFORE /:id so "user" isn't captured as an order id.
r.get("/user/:userId", asyncH(async (req, res) => {
  const limit = Math.min(Number(req.query.limit) || 5, 20);
  const orders = await Order.find({ userId: req.params.userId })
    .sort({ placedAt: -1 }).limit(limit).lean();
  res.json({
    count: orders.length,
    orders: orders.map((o) => ({
      orderId: String(o._id), placedAt: o.placedAt, status: o.status,
      total: o.totals?.grandTotal,
      items: (o.items || []).map((i) => ({ name_vi: i.name_vi, qty: i.qty })),
    })),
  });
}));

// GET /api/orders/user/:userId/last-basket — re-orderable basket from the
// member's last order, falling back to their last (seeded) transaction so
// "đặt lại đơn cũ" works for demo members who haven't ordered live yet.
// Transaction lines carry skus only → resolve to productIds here.
r.get("/user/:userId/last-basket", asyncH(async (req, res) => {
  const userId = req.params.userId;
  const lastOrder = await Order.findOne({ userId }).sort({ placedAt: -1 }).lean();
  let source, rawItems;
  if (lastOrder) {
    source = "order";
    rawItems = (lastOrder.items || []).map((i) => ({ sku: i.sku, productId: i.productId, name_vi: i.name_vi, qty: i.qty }));
  } else {
    const lastTx = await Transaction.findOne({ userId }).sort({ ts: -1 }).lean();
    if (!lastTx) return res.json({ found: false, items: [] });
    source = "transaction";
    rawItems = (lastTx.lines || []).map((l) => ({ sku: l.sku, name_vi: l.name_vi, qty: l.qty }));
  }
  const skus = rawItems.filter((i) => !i.productId).map((i) => i.sku);
  const prods = skus.length ? await Product.find({ sku: { $in: skus }, available: true }).lean() : [];
  const bySku = Object.fromEntries(prods.map((p) => [p.sku, p]));
  const items = rawItems
    .map((i) => ({ ...i, productId: i.productId ? String(i.productId) : (bySku[i.sku] ? String(bySku[i.sku]._id) : null) }))
    .filter((i) => i.productId);
  res.json({ found: items.length > 0, source, items });
}));

// POST /api/orders  {cartId, idempotencyKey, payment}
r.post("/", asyncH(async (req, res) => {
  const { cartId, idempotencyKey, payment } = req.body || {};
  const result = await placeOrder({ cartId, idempotencyKey, payment });
  if (!result.deduped) {
    await Event.create({
      type: "order_placed", channel: result.order.channel, cartId,
      userId: result.order.userId, payload: { grandTotal: result.order.totals.grandTotal },
    });
  }
  res.status(result.deduped ? 200 : 201).json({ order: result.order, deduped: result.deduped, pointsEarned: result.order.pointsEarned });
}));

// POST /api/orders/:id/pay — settle a pending (QR) order. Idempotent: paying an
// already-paid order just returns it. Called by the reco /zalo/pay webhook.
r.post("/:id/pay", asyncH(async (req, res) => {
  const order = await Order.findById(req.params.id);
  if (!order) throw httpError(404, "order_not_found");
  const already = order.payment?.status === "paid";
  if (!already) {
    order.payment.status = "paid";
    order.payment.paidAt = new Date();
    order.status = "paid";
    await order.save();
    await Event.create({
      type: "payment_settled", channel: order.channel, userId: order.userId,
      payload: { orderId: String(order._id), method: order.payment?.method, grandTotal: order.totals?.grandTotal },
    });
  }
  res.json({ order, alreadyPaid: already });
}));

r.get("/:id", asyncH(async (req, res) => {
  const order = await Order.findById(req.params.id).lean();
  if (!order) throw httpError(404, "order_not_found");
  res.json(order);
}));

export default r;
