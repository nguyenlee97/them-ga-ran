import mongoose from "mongoose";

const StatsSchema = new mongoose.Schema(
  {
    visitCount: { type: Number, default: 0 },
    totalOrders: { type: Number, default: 0 },
    totalSpend: { type: Number, default: 0 }, // VND
    firstOrderAt: Date,
    lastOrderAt: Date,
  },
  { _id: false }
);

const TIER_RATES = { member: 0.03, gold: 0.05, platinum: 0.07 };

const UserSchema = new mongoose.Schema(
  {
    phone: { type: String, required: true, unique: true, index: true },
    name: String,
    tier: { type: String, enum: ["member", "gold", "platinum"], default: "member" },
    pointsBalance: { type: Number, default: 0 },
    birthday: Date,
    favorites: { type: [String], default: [] }, // product skus
    stats: { type: StatsSchema, default: () => ({}) },
  },
  { timestamps: true }
);

UserSchema.methods.earnRate = function () {
  return TIER_RATES[this.tier] ?? 0.03;
};

UserSchema.statics.TIER_RATES = TIER_RATES;

export default mongoose.model("User", UserSchema);
