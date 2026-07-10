import { Router } from "express";
import Cart from "../models/Cart.js";
import Voucher from "../models/Voucher.js";
import { recalcCart } from "../services/cartService.js";
import { asyncH, httpError } from "../middleware/error.js";

const r = Router();

/**
 * Stubbed voucher application (full promo-rule engine deferred).
 * Supports percent / amount. Validates min order + active window only.
 */
r.post("/carts/:id/apply", asyncH(async (req, res) => {
  const { code } = req.body || {};
  const cart = await Cart.findById(req.params.id);
  if (!cart) throw httpError(404, "cart_not_found");
  const v = await Voucher.findOne({ code: (code || "").toUpperCase(), active: true });
  if (!v) return res.status(200).json({ applied: false, reason: "invalid_or_inactive_code", cart });

  const now = new Date();
  if ((v.validFrom && now < v.validFrom) || (v.validTo && now > v.validTo))
    return res.status(200).json({ applied: false, reason: "out_of_window", cart });
  if (cart.totals.subtotal < (v.conditions?.minOrder || 0))
    return res.status(200).json({ applied: false, reason: "min_order_not_met", minOrder: v.conditions.minOrder, cart });

  const discount = v.type === "percent"
    ? Math.round((cart.totals.subtotal * v.value) / 100)
    : v.value;

  cart.appliedVouchers = [{ code: v.code, type: v.type, discount, note: v.description }];
  recalcCart(cart);
  await cart.save();
  res.json({ applied: true, discount, cart });
}));

r.get("/", asyncH(async (req, res) => {
  const vouchers = await Voucher.find({ active: true }).lean();
  res.json({ count: vouchers.length, vouchers });
}));

export default r;
