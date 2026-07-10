import mongoose from "mongoose";

const StoreSchema = new mongoose.Schema(
  {
    code: { type: String, unique: true, index: true },
    name: { type: String, required: true },
    address: String,
    district: String,
    city: String,
    type: { type: String, enum: ["mall", "standalone"], default: "standalone" },
    hours: { open: { type: String, default: "09:00" }, close: { type: String, default: "22:00" } },
    kioskIds: { type: [String], default: [] },
    lat: Number,
    lng: Number,
  },
  { timestamps: true }
);

export default mongoose.model("Store", StoreSchema);
