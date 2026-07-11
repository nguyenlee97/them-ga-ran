import mongoose from "mongoose";

const OrderSchema = new mongoose.Schema(
  {
    idempotencyKey: { type: String, required: true, unique: true, index: true },
    cartId: { type: mongoose.Schema.Types.ObjectId, ref: "Cart" },
    channel: { type: String, enum: ["kiosk", "zalo", "messenger"], default: "kiosk" },
    storeId: { type: mongoose.Schema.Types.ObjectId, ref: "Store" },
    dineMode: { type: String, enum: ["dine_in", "takeaway", "delivery"], default: "dine_in" },
    userId: { type: mongoose.Schema.Types.ObjectId, ref: "User", default: null },
    deliveryAddress: { type: String, default: null },
    contactName: { type: String, default: null },
    contactPhone: { type: String, default: null },
    items: { type: Array, default: [] }, // snapshot of cart lines
    appliedVouchers: { type: Array, default: [] },
    totals: {
      subtotal: Number,
      discount: Number,
      grandTotal: Number,
    },
    payment: {
      method: { type: String, enum: ["mock", "cod", "qr"], default: "mock" },
      status: { type: String, enum: ["pending", "paid", "failed"], default: "pending" },
      paidAt: Date,
    },
    pointsEarned: { type: Number, default: 0 },
    status: {
      type: String,
      enum: ["created", "paid", "preparing", "ready", "completed", "cancelled"],
      default: "created",
    },
    placedAt: { type: Date, default: Date.now },
  },
  { timestamps: true }
);

export default mongoose.model("Order", OrderSchema);
