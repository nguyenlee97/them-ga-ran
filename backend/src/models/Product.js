import mongoose from "mongoose";

const ModifierOption = new mongoose.Schema(
  { name_vi: String, name_en: String, priceDelta: { type: Number, default: 0 } },
  { _id: false }
);
const ModifierGroup = new mongoose.Schema(
  { group: String, min: { type: Number, default: 0 }, max: { type: Number, default: 1 }, options: [ModifierOption] },
  { _id: false }
);
const ComboItem = new mongoose.Schema(
  { sku: String, qty: { type: Number, default: 1 }, note: String },
  { _id: false }
);

const ProductSchema = new mongoose.Schema(
  {
    sku: { type: String, required: true, unique: true, index: true },
    name_vi: { type: String, required: true },
    name_en: String,
    category: { type: String, index: true }, // "Gà Rán", "Combo 1 Người", ...
    price: { type: Number, required: true }, // VND
    oldPrice: { type: Number, default: null }, // strike-through original price
    code: { type: String }, // KFC item code (image key)
    imageUrl: String,
    description: String,
    nutrition: { kcal: Number, protein: Number, fat: Number, carb: Number },
    tags: { type: [String], default: [] }, // spicy | light | new | bestseller | drink | side | dessert
    isCombo: { type: Boolean, default: false },
    comboItems: [ComboItem],
    modifiers: [ModifierGroup],
    available: { type: Boolean, default: true },
    storeAvailability: { type: [String], default: [] }, // empty = all stores
    promoIds: { type: [String], default: [] },
    sortOrder: { type: Number, default: 0 },
  },
  { timestamps: true }
);

export default mongoose.model("Product", ProductSchema);
