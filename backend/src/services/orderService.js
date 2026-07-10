import Order from "../models/Order.js";
import Cart from "../models/Cart.js";
import User from "../models/User.js";
import { applyOrderToStats } from "./loyaltyService.js";
import { httpError } from "../middleware/error.js";

/**
 * Idempotent order commit. Same idempotencyKey => same order returned, never
 * double-charged (unique index on idempotencyKey). Mirrors Claw-a-thon order_api.
 */
export async function placeOrder({ cartId, idempotencyKey, payment = {} }) {
  if (!idempotencyKey) throw httpError(400, "missing_idempotency_key");

  // Fast path: already committed with this key.
  const existing = await Order.findOne({ idempotencyKey });
  if (existing) return { order: existing, deduped: true };

  const cart = await Cart.findById(cartId);
  if (!cart) throw httpError(404, "cart_not_found", cartId);
  if (cart.status === "ordered") throw httpError(409, "cart_already_ordered", cartId);
  if (!cart.items.length) throw httpError(400, "cart_empty");

  // Build order snapshot. Payment is mocked → mark paid immediately.
  const orderDoc = {
    idempotencyKey,
    cartId: cart._id,
    channel: cart.channel,
    storeId: cart.storeId,
    dineMode: cart.dineMode,
    userId: cart.userId || null,
    items: cart.items,
    appliedVouchers: cart.appliedVouchers,
    totals: cart.totals,
    payment: { method: payment.method || "mock", status: "paid", paidAt: new Date() },
    status: "paid",
    placedAt: new Date(),
  };

  let pointsEarned = 0;
  let user = null;
  if (cart.userId) {
    user = await User.findById(cart.userId);
    if (user) pointsEarned = applyOrderToStats(user, { totals: cart.totals });
  }
  orderDoc.pointsEarned = pointsEarned;

  let order;
  try {
    order = await Order.create(orderDoc);
  } catch (e) {
    // Duplicate key (race): another request committed the same key first.
    if (e.code === 11000) {
      const dup = await Order.findOne({ idempotencyKey });
      if (dup) return { order: dup, deduped: true };
    }
    throw e;
  }

  // Persist side effects only after the order is safely written.
  if (user) await user.save();
  cart.status = "ordered";
  await cart.save();

  return { order, deduped: false, pointsEarned };
}
