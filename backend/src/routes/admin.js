import { Router } from "express";
import Product from "../models/Product.js";
import Store from "../models/Store.js";
import User from "../models/User.js";
import Transaction from "../models/Transaction.js";
import AssocRule from "../models/AssocRule.js";
import Order from "../models/Order.js";
import { asyncH } from "../middleware/error.js";

const r = Router();

// Quick inspection endpoints for demo/debugging.
r.get("/stats", asyncH(async (req, res) => {
  const [products, stores, users, transactions, rules, orders] = await Promise.all([
    Product.countDocuments(), Store.countDocuments(), User.countDocuments(),
    Transaction.countDocuments(), AssocRule.countDocuments(), Order.countDocuments(),
  ]);
  res.json({ products, stores, users, transactions, assocRules: rules, orders });
}));

r.get("/rules", asyncH(async (req, res) => {
  const rules = await AssocRule.find().sort({ lift: -1 }).limit(Number(req.query.limit) || 50).lean();
  res.json({ count: rules.length, rules });
}));

export default r;
