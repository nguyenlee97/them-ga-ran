import { nanoid } from "nanoid";
import Product from "../models/Product.js";
import { httpError } from "../middleware/error.js";

/** Recompute line + cart totals server-side. Never trust the client. */
export function recalcCart(cart) {
  let subtotal = 0;
  for (const line of cart.items) {
    const modSum = (line.modifiers || []).reduce((s, m) => s + (m.priceDelta || 0), 0);
    line.lineTotal = (line.unitPrice + modSum) * line.qty;
    subtotal += line.lineTotal;
  }
  const discount = (cart.appliedVouchers || []).reduce((s, v) => s + (v.discount || 0), 0);
  cart.totals.subtotal = subtotal;
  cart.totals.discount = Math.min(discount, subtotal);
  cart.totals.grandTotal = Math.max(0, subtotal - cart.totals.discount);
  return cart;
}

/** Add a line, snapshotting the current product price. */
export async function addItem(cart, { productId, qty = 1, modifiers = [] }) {
  const product = await Product.findById(productId);
  if (!product) throw httpError(404, "product_not_found", `No product ${productId}`);
  if (!product.available) throw httpError(409, "product_unavailable", product.name_vi);

  cart.items.push({
    lineId: nanoid(10),
    productId: product._id,
    sku: product.sku,
    name_vi: product.name_vi,
    imageUrl: product.imageUrl,
    qty,
    unitPrice: product.price,
    modifiers,
    lineTotal: 0,
  });
  return recalcCart(cart);
}

export function setItemQty(cart, lineId, qty) {
  const line = cart.items.find((l) => l.lineId === lineId);
  if (!line) throw httpError(404, "line_not_found", lineId);
  if (qty <= 0) return removeItem(cart, lineId);
  line.qty = qty;
  return recalcCart(cart);
}

export function removeItem(cart, lineId) {
  const before = cart.items.length;
  cart.items = cart.items.filter((l) => l.lineId !== lineId);
  if (cart.items.length === before) throw httpError(404, "line_not_found", lineId);
  return recalcCart(cart);
}
