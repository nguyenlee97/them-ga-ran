import mongoose from "mongoose";

// Chat agent conversation memory (P4).
const SessionSchema = new mongoose.Schema(
  {
    sessionId: { type: String, unique: true, index: true },
    channel: { type: String, default: "zalo" },
    externalId: String, // zaloUserId
    userId: { type: mongoose.Schema.Types.ObjectId, ref: "User", default: null },
    cartId: { type: mongoose.Schema.Types.ObjectId, ref: "Cart", default: null },
    messages: { type: Array, default: [] }, // [{role, content, tool_calls?}]
    state: { type: Object, default: {} },
  },
  { timestamps: true }
);

export default mongoose.model("Session", SessionSchema);
