import { Router } from "express";
import Product from "../models/Product.js";
import { asyncH, httpError } from "../middleware/error.js";

const r = Router();

// GET /api/menu?category=&tag=  → full catalog (grouped-friendly)
r.get("/", asyncH(async (req, res) => {
  const q = { available: true };
  if (req.query.category) q.category = req.query.category;
  if (req.query.tag) q.tags = req.query.tag;
  const items = await Product.find(q).sort({ sortOrder: 1, category: 1 }).lean();
  res.json({ count: items.length, items });
}));

// GET /api/menu/categories → distinct categories in menu order
r.get("/categories", asyncH(async (req, res) => {
  const cats = await Product.distinct("category", { available: true });
  res.json({ categories: cats });
}));

// GET /api/menu/search?q=&category=&maxPrice=
// Text-ish search now; the reco service adds embedding search later.
r.get("/search", asyncH(async (req, res) => {
  const { q = "", category, maxPrice } = req.query;
  const filter = { available: true };
  if (category) filter.category = category;
  if (maxPrice) filter.price = { $lte: Number(maxPrice) };
  if (q) {
    const rx = new RegExp(q.trim().replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "i");
    filter.$or = [{ name_vi: rx }, { name_en: rx }, { description: rx }, { tags: rx }];
  }
  const items = await Product.find(filter).limit(30).lean();
  res.json({ count: items.length, items });
}));

// GET /api/menu/:id
r.get("/:id", asyncH(async (req, res) => {
  const item = await Product.findById(req.params.id).lean();
  if (!item) throw httpError(404, "product_not_found", req.params.id);
  res.json(item);
}));

export default r;
