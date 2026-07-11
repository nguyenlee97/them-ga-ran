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
// Token-scored, diacritic-insensitive search ("ga gion cay" works too).
// Name hits rank far above description hits so "pepsi" returns the DRINK
// before combos that merely mention Pepsi in their description.
const _strip = (s) => (s || "").toLowerCase().normalize("NFD")
  .replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d");

r.get("/search", asyncH(async (req, res) => {
  const { q = "", category, maxPrice } = req.query;
  const filter = { available: true };
  if (maxPrice) filter.price = { $lte: Number(maxPrice) };
  let all = await Product.find(filter).lean();
  if (category) {
    const c = _strip(category);
    all = all.filter((p) => _strip(p.category).includes(c));
  }
  const tokens = _strip(q).split(/\s+/).filter(Boolean);
  if (!tokens.length) return res.json({ count: Math.min(all.length, 30), items: all.slice(0, 30) });

  const scored = [];
  for (const p of all) {
    const name = _strip(p.name_vi) + " " + _strip(p.name_en);
    const tags = _strip((p.tags || []).join(" "));
    const cat = _strip(p.category);
    const desc = _strip(p.description);
    let score = 0;
    for (const t of tokens) {
      if (name.includes(t)) score += 10;
      else if (tags.includes(t)) score += 4;
      else if (cat.includes(t)) score += 3;
      else if (desc.includes(t)) score += 1;
    }
    if (score > 0) scored.push([score, p]);
  }
  scored.sort((a, b) => b[0] - a[0]);
  const items = scored.slice(0, 30).map((x) => x[1]);
  res.json({ count: items.length, items });
}));

// GET /api/menu/:id
r.get("/:id", asyncH(async (req, res) => {
  const item = await Product.findById(req.params.id).lean();
  if (!item) throw httpError(404, "product_not_found", req.params.id);
  res.json(item);
}));

export default r;
