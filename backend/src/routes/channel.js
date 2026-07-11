import { Router } from "express";
import ChannelIdentity from "../models/ChannelIdentity.js";
import User from "../models/User.js";
import { loyaltySummary } from "../services/loyaltyService.js";
import { asyncH, httpError } from "../middleware/error.js";

const r = Router();

/**
 * Channel identity — the durable zaloIdByOA → KFC member mapping.
 *
 * Flow (P4): every incoming chat message resolves the sender's OA-scoped id.
 * Linked → the agent knows the member instantly (personalization, loyalty,
 * reorder). Not linked → the agent pitches linking ONCE (ưu đãi, tích điểm,
 * gợi ý đúng gu); ordering still works anonymously.
 */

// GET /api/channel/resolve/:channel/:externalId
r.get("/resolve/:channel/:externalId", asyncH(async (req, res) => {
  const { channel, externalId } = req.params;
  const ident = await ChannelIdentity.findOne({ channel, externalId }).lean();
  if (!ident || ident.status !== "linked" || !ident.userId) {
    return res.json({ linked: false });
  }
  const user = await User.findById(ident.userId);
  if (!user) return res.json({ linked: false });
  res.json({
    linked: true,
    user: { id: user._id, phone: user.phone, name: user.name, tier: user.tier },
    loyalty: loyaltySummary(user),
  });
}));

// POST /api/channel/link {channel, externalId, phone, name?}
// Phone-only on chat channels (no OTP — Zalo already authenticates the user, and
// the number just links them to a member). Creates the member if new; upserts the
// mapping (unique index on channel+externalId → idempotent, re-link overwrites).
r.post("/link", asyncH(async (req, res) => {
  const { channel, externalId, phone, name } = req.body || {};
  if (!channel || !externalId) throw httpError(400, "missing_channel_identity");
  if (!phone) throw httpError(400, "missing_phone", "phone required");

  let user = await User.findOne({ phone });
  if (!user) user = await User.create({ phone, name: name || "Thành Viên KFC" });

  await ChannelIdentity.findOneAndUpdate(
    { channel, externalId },
    { $set: { phone, userId: user._id, status: "linked", linkedAt: new Date() } },
    { upsert: true, new: true }
  );

  res.json({
    linked: true,
    user: { id: user._id, phone: user.phone, name: user.name, tier: user.tier },
    loyalty: loyaltySummary(user),
  });
}));

// POST /api/channel/unlink {channel, externalId} — "hủy liên kết"
r.post("/unlink", asyncH(async (req, res) => {
  const { channel, externalId } = req.body || {};
  if (!channel || !externalId) throw httpError(400, "missing_channel_identity");
  await ChannelIdentity.findOneAndUpdate(
    { channel, externalId },
    { $set: { status: "pending", userId: null, phone: null } }
  );
  res.json({ linked: false });
}));

export default r;
