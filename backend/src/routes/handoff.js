import { Router } from "express";
import Event from "../models/Event.js";
import { asyncH } from "../middleware/error.js";

const r = Router();

/**
 * POST /api/handoff — chat agent escalates to a human (complaint, payment
 * dispute, allergen question, repeated NLU failure, user asks for human).
 * For now we just record it; a real routing/notify hook comes later.
 */
r.post("/", asyncH(async (req, res) => {
  const { reason, transcript, channel, externalId, sessionId } = req.body || {};
  await Event.create({ type: "handoff", channel, payload: { reason, sessionId, externalId, transcript } });
  res.status(201).json({ ok: true, message: "Đã chuyển cho nhân viên hỗ trợ. Vui lòng chờ trong giây lát." });
}));

export default r;
