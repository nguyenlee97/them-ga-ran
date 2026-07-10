import mongoose from "mongoose";

/**
 * Maps an external chat identity (e.g. Zalo OA-scoped user id) to a KFC member.
 * Zalo OA never exposes the real phone number, so we ask for it once and link.
 */
const ChannelIdentitySchema = new mongoose.Schema(
  {
    channel: { type: String, enum: ["zalo", "messenger"], required: true },
    externalId: { type: String, required: true }, // zaloUserId by OA
    phone: String,
    userId: { type: mongoose.Schema.Types.ObjectId, ref: "User" },
    status: { type: String, enum: ["pending", "linked"], default: "pending" },
    linkedAt: Date,
  },
  { timestamps: true }
);

ChannelIdentitySchema.index({ channel: 1, externalId: 1 }, { unique: true });

export default mongoose.model("ChannelIdentity", ChannelIdentitySchema);
