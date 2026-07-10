import { Router } from "express";
import Cart from "../models/Cart.js";
import { addItem, removeItem, recalcCart } from "../services/cartService.js";
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

// DELETE /api/carts/:id/items/:lineId
r.delete("/:id/items/:lineId", asyncH(async (req, res) => {
  const cart = await Cart.findById(req.params.id);
  if (!cart) throw httpError(404, "cart_not_found");
  removeItem(cart, req.params.lineId);
  await cart.save();
  res.json(cart);
}));

// PATCH /api/carts/:id  {dineMode?, userId?}  — attach member after login, etc.
r.patch("/:id", asyncH(async (req, res) => {
  const cart = await Cart.findById(req.params.id);
  if (!cart) throw httpError(404, "cart_not_found");
  const { dineMode, userId } = req.body || {};
  if (dineMode) cart.dineMode = dineMode;
  if (userId !== undefined) cart.userId = userId;
  recalcCart(cart);
  await cart.save();
  res.json(cart);
}));

export default r;
