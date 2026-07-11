import { Router } from "express";
import Cart from "../models/Cart.js";
import { addItem, removeItem, setItemQty, recalcCart } from "../services/cartService.js";
import { asyncH, httpError } from "../middleware/error.js";

const r = Router();

// POST /api/carts  {channel, storeId, dineMode, userId?}
r.post("/", asyncH(async (req, res) => {
  const { channel = "kiosk", storeId, dineMode = "dine_in", userId = null } = req.body || {};
  const cart = await Cart.create({ channel, storeId, dineMode, userId });
  res.status(201).json(cart);
}));

r.get("/:id", asyncH(async (req, res) => {
  const cart = await Cart.findById(req.params.id);
  if (!cart) throw httpError(404, "cart_not_found");
  res.json(cart);
}));

// POST /api/carts/:id/items  {productId, qty, modifiers}
r.post("/:id/items", asyncH(async (req, res) => {
  const cart = await Cart.findById(req.params.id);
  if (!cart) throw httpError(404, "cart_not_found");
  if (cart.status !== "open") throw httpError(409, "cart_not_open");
  await addItem(cart, req.body || {});
  await cart.save();
  res.json(cart);
}));

// PATCH /api/carts/:id/items/:lineId  {qty}  — set absolute line quantity
r.patch("/:id/items/:lineId", asyncH(async (req, res) => {
  const cart = await Cart.findById(req.params.id);
  if (!cart) throw httpError(404, "cart_not_found");
  const qty = Number(req.body?.qty);
  if (!Number.isFinite(qty)) throw httpError(400, "invalid_qty");
  setItemQty(cart, req.params.lineId, qty);
  await cart.save();
  res.json(cart);
}));

// DELETE /api/carts/:id/items/:lineId
r.delete("/:id/items/:lineId", asyncH(async (req, res) => {
  const cart = await Cart.findById(req.params.id);
  if (!cart) throw httpError(404, "cart_not_found");
  removeItem(cart, req.params.lineId);
  await cart.save();
  res.json(cart);
}));

// PATCH /api/carts/:id  {dineMode?, userId?, deliveryAddress?, contactName?, contactPhone?}
// Attach member after login, set delivery details, etc.
r.patch("/:id", asyncH(async (req, res) => {
  const cart = await Cart.findById(req.params.id);
  if (!cart) throw httpError(404, "cart_not_found");
  const { dineMode, userId, deliveryAddress, contactName, contactPhone } = req.body || {};
  if (dineMode) cart.dineMode = dineMode;
  if (userId !== undefined) cart.userId = userId;
  if (deliveryAddress !== undefined) {
    cart.deliveryAddress = deliveryAddress;
    cart.dineMode = "delivery"; // giving an address implies delivery
  }
  if (contactName !== undefined) cart.contactName = contactName;
  if (contactPhone !== undefined) cart.contactPhone = contactPhone;
  recalcCart(cart);
  await cart.save();
  res.json(cart);
}));

export default r;
