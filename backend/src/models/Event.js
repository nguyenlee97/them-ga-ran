import mongoose from "mongoose";

/**
 * Telemetry: recommendation impressions/accepts/declines + generic events.
 * Powers AOV-uplift measurement and (later) the contextual bandit.
 */
const EventSchema = new mongoose.Schema(
  {
    type: { type: String, index: true }, // reco_shown | reco_accepted | reco_declined | order_placed | ...
    slot: String, // cart | item_added | checkout | browse | greeting
    strategy: String, // assoc_rule | context_pop | embedding | personalize | llm_rerank
    channel: String,
    cartId: { type: mongoose.Schema.Types.ObjectId, ref: "Cart" },
    userId: { type: mongoose.Schema.Types.ObjectId, ref: "User", default: null },
    productId: String,
    payload: { type: Object, default: {} },
    ts: { type: Date, default: Date.now, index: true },
  },
  { timestamps: true }
);

export default mongoose.model("Event", EventSchema);
