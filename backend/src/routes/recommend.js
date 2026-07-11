import { Router } from "express";
import Cart from "../models/Cart.js";
import Event from "../models/Event.js";
import Product from "../models/Product.js";
import { getRecommendations } from "../services/recoClient.js";
import { asyncH } from "../middleware/error.js";

const r = Router();

/**
 * POST /api/recommend — single reco surface for kiosk + chat.
 * Body: { slot, context:{storeId,dineMode,timeOfDay,dayOfWeek,channel,cart,userId}, limit }
 * If a cartId is passed instead of an inline cart, we hydrate it server-side.
 */
r.post("/", asyncH(async (req, res) => {
  const body = req.body || {};
  const ctx = body.context || {};

  // Allow caller to pass cartId; hydrate cart lines for the reco service.
  if (ctx.cartId && !ctx.cart) {
    const cart = await Cart.findById(ctx.cartId).lean();
    if (cart) {
      ctx.cart = cart.items.map((i) => ({ productId: String(i.productId), sku: i.sku, qty: i.qty }));
      ctx.userId = ctx.userId ?? (cart.userId ? String(cart.userId) : null);
      ctx.dineMode = ctx.dineMode || cart.dineMode;
      ctx.storeId = ctx.storeId || (cart.storeId ? String(cart.storeId) : null);
      ctx.channel = ctx.channel || cart.channel;
    }
  }
  body.context = ctx;

  const result = await getRecommendations(body);

  // Enrich with live product docs (price/image) in case reco returns skus only.
  const skus = (result.recommendations || []).map((x) => x.sku).filter(Boolean);
  if (skus.length) {
    const prods = await Product.find({ sku: { $in: skus } }).lean();
    const bySku = Object.fromEntries(prods.map((p) => [p.sku, p]));
    result.recommendations = result.recommendations.map((rec) => {
      const p = bySku[rec.sku];
      return p ? { ...rec, productId: String(p._id), name: rec.name || p.name_vi, price: rec.price ?? p.price, imageUrl: p.imageUrl } : rec;
    });
  }
  if (skus.length || result.comboUpsell) {
    await Event.create({
      type: "reco_shown", slot: body.slot, channel: ctx.channel,
      userId: ctx.userId || null, cartId: ctx.cartId || null,
      payload: {
        strategies: result.explain?.strategies_used, items: skus,
        combo: result.comboUpsell?.sku || null,
      },
    });
  }

  res.json(result);
}));

export default r;
