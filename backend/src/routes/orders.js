import { Router } from "express";
import Order from "../models/Order.js";
import Event from "../models/Event.js";
import { placeOrder } from "../services/orderService.js";
import { asyncH, httpError } from "../middleware/error.js";

const r = Router();

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

r.get("/:id", asyncH(async (req, res) => {
  const order = await Order.findById(req.params.id).lean();
  if (!order) throw httpError(404, "order_not_found");
  res.json(order);
}));

export default r;
