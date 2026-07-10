import mongoose from "mongoose";

/**
 * Synthetic POS history — the fuel for association-rule mining.
 * Line-item level. Replaceable by KFC's real export via a single adapter.
 */
const TxLine = new mongoose.Schema(
  { sku: String, name_vi: String, category: String, qty: { type: Number, default: 1 }, unitPrice: Number },
  { _id: false }
);

const TransactionSchema = new mongoose.Schema(
  {
    externalId: String, // original POS id if imported
    storeId: { type: mongoose.Schema.Types.ObjectId, ref: "Store", index: true },
    storeType: { type: String, enum: ["mall", "standalone"] },
    userId: { type: mongoose.Schema.Types.ObjectId, ref: "User", default: null },
    ts: { type: Date, index: true },
    timeOfDay: { type: String, enum: ["breakfast", "lunch", "afternoon", "dinner", "late"], index: true },
    dayOfWeek: String, // Mon..Sun
    dineMode: { type: String, enum: ["dine_in", "takeaway"] },
    channel: { type: String, default: "kiosk" },
    lines: { type: [TxLine], default: [] },
    total: Number,
  },
  { timestamps: true }
);

export default mongoose.model("Transaction", TransactionSchema);
