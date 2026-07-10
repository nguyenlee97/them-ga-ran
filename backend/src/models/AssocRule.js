import mongoose from "mongoose";

/**
 * Precomputed market-basket rules {antecedent} -> consequent.
 * Written by reco/app/mine_rules.py, read by the reco service at serve time.
 */
const AssocRuleSchema = new mongoose.Schema(
  {
    antecedent: { type: [String], index: true }, // sorted skus
    consequent: { type: String, index: true }, // sku
    support: Number,
    confidence: Number,
    lift: Number,
    context: {
      timeOfDay: { type: String, default: "any" },
      dineMode: { type: String, default: "any" },
    },
  },
  { timestamps: true }
);

AssocRuleSchema.index({ "context.timeOfDay": 1, "context.dineMode": 1, confidence: -1 });

export default mongoose.model("AssocRule", AssocRuleSchema);
