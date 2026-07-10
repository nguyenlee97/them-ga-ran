import { Router } from "express";
import Event from "../models/Event.js";
import { asyncH } from "../middleware/error.js";

const r = Router();

// POST /api/events — client logs reco_accepted / reco_declined / etc.
r.post("/", asyncH(async (req, res) => {
  const e = await Event.create(req.body || {});
  res.status(201).json({ id: e._id });
}));

export default r;
