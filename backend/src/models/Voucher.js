import mongoose from "mongoose";

// Stubbed for now — full promo-rule engine deferred until KFC data.
const VoucherSchema = new mongoose.Schema(
  {
    code: { type: String, unique: true, index: true },
    description: String,
    type: { type: String, enum: ["percent", "amount", "freeItem", "combo"], default: "amount" },
    value: { type: Number, default: 0 }, // percent (0-100) or VND amount
    conditions: {
      minOrder: { type: Number, default: 0 },
      items: { type: [String], default: [] },
      tier: { type: String, default: "any" },
      channel: { type: String, default: "any" },
    },
    validFrom: Date,
    validTo: Date,
    active: { type: Boolean, default: true },
  },
  { timestamps: true }
);

export default mongoose.model("Voucher", VoucherSchema);
