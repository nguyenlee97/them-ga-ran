import { Router } from "express";
import Store from "../models/Store.js";
import { asyncH } from "../middleware/error.js";

const r = Router();

r.get("/", asyncH(async (req, res) => {
  const q = {};
  if (req.query.city) q.city = req.query.city;
  const stores = await Store.find(q).lean();
  res.json({ count: stores.length, stores });
}));

r.get("/:id", asyncH(async (req, res) => {
  const s = await Store.findById(req.params.id).lean();
  res.json(s || {});
}));

export default r;
