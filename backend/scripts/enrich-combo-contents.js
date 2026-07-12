/**
 * Non-destructive live migration: enrich existing Product documents in place.
 * It preserves product _ids, so carts/orders/recommendation rules stay valid.
 *
 * Usage: npm run menu:enrich-combos
 */
import "dotenv/config";
import mongoose from "mongoose";
import { connectDB } from "../src/db.js";
import Product from "../src/models/Product.js";
import { comboItemsFromDescription } from "../src/services/comboContents.js";

try {
  await connectDB();
  const combos = await Product.find({
    isCombo: true,
    description: { $exists: true, $ne: "" },
  }, { sku: 1, description: 1 }).lean();
  const ops = combos.map((item) => ({
    updateOne: {
      filter: { sku: item.sku },
      update: { $set: {
        description: item.description,
        comboItems: comboItemsFromDescription(item.description),
      } },
    },
  }));
  const result = ops.length ? await Product.bulkWrite(ops) : null;
  console.log(`[menu:enrich-combos] combos=${ops.length} matched=${result?.matchedCount || 0} modified=${result?.modifiedCount || 0}`);
} finally {
  await mongoose.disconnect();
}
