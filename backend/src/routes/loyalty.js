import { Router } from "express";
import User from "../models/User.js";
import { loyaltySummary } from "../services/loyaltyService.js";
import { asyncH, httpError } from "../middleware/error.js";

const r = Router();

// GET /api/loyalty/:userId → simple member stats (times eaten, cumulative, rank, points)
r.get("/:userId", asyncH(async (req, res) => {
  const user = await User.findById(req.params.userId);
  if (!user) throw httpError(404, "user_not_found");
  res.json(loyaltySummary(user));
}));

export default r;
