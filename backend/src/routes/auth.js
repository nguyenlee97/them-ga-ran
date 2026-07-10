import { Router } from "express";
import User from "../models/User.js";
import { loyaltySummary } from "../services/loyaltyService.js";
import { asyncH, httpError } from "../middleware/error.js";

const r = Router();

/**
 * Mock login by phone + code (kiosk member QR / phone, chat phone-link).
 * Any non-empty code passes for the demo. Creates the member if new.
 */
r.post("/login", asyncH(async (req, res) => {
  const { phone, code, name } = req.body || {};
  if (!phone || !code) throw httpError(400, "missing_credentials", "phone and code required");
  let user = await User.findOne({ phone });
  if (!user) user = await User.create({ phone, name: name || "Thành Viên KFC" });
  res.json({ user: { id: user._id, phone: user.phone, name: user.name, tier: user.tier }, loyalty: loyaltySummary(user) });
}));

r.get("/me/:userId", asyncH(async (req, res) => {
  const user = await User.findById(req.params.userId);
  if (!user) throw httpError(404, "user_not_found");
  res.json({ user: { id: user._id, phone: user.phone, name: user.name, tier: user.tier }, loyalty: loyaltySummary(user) });
}));

export default r;
