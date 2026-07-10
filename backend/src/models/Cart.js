import mongoose from "mongoose";

const CartLine = new mongoose.Schema(
  {
    lineId: { type: String, required: true }, // nanoid, stable per line
    productId: { type: mongoose.Schema.Types.ObjectId, ref: "Product", required: true },
    sku: String,
    name_vi: String,
    imageUrl: String,
    qty: { type: Number, default: 1, min: 1 },
    unitPrice: { type: Number, required: true }, // snapshot at add time
    modifiers: { type: Array, default: [] }, // [{group, name_vi, priceDelta}]
    lineTotal: { type: Number, default: 0 },
  },
  { _id: false }
);

const AppliedVoucher = new mongoose.Schema(
  { code: String, type: String, discount: { type: Number, default: 0 }, note: String },
  { _id: false }
);

const CartSchema = new mongoose.Schema(
  {
    channel: { type: String, enum: ["kiosk", "zalo", "messenger"], default: "kiosk" },
    storeId: { type: mongoose.Schema.Types.ObjectId, ref: "Store" },
    dineMode: { type: String, enum: ["dine_in", "takeaway"], default: "dine_in" },
    userId: { type: mongoose.Schema.Types.ObjectId, ref: "User", default: null }, // null = anonymous
    items: { type: [CartLine], default: [] },
    appliedVouchers: { type: [AppliedVoucher], default: [] },
    totals: {
      subtotal: { type: Number, default: 0 },
      discount: { type: Number, default: 0 },
      grandTotal: { type: Number, default: 0 },
    },
    status: { type: String, enum: ["open", "ordered", "abandoned"], default: "open", index: true },
  },
  { timestamps: true }
);

export default mongoose.model("Cart", CartSchema);
