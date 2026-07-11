import Transaction from "../models/Transaction.js";
import Product from "../models/Product.js";
import Store from "../models/Store.js";

const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function timeOfDay(hour) {
  if (hour < 10) return "breakfast";
  if (hour < 14) return "lunch";
  if (hour < 17) return "afternoon";
  if (hour < 21) return "dinner";
  return "late";
}

/**
 * Order → transactions feedback loop.
 *
 * Every committed order is appended to `transactions` — the same collection
 * the reco engine's personalization (L4) and rule mining read. So a logged-in
 * member's purchase immediately shapes their future recommendations, and
 * anonymous orders still grow the mining corpus. With no organizer data, the
 * live system generates its own training data.
 *
 * Fire-and-forget by design: a failure here must NEVER break checkout.
 */
export async function appendOrderTransaction(order) {
  try {
    const skus = order.items.map((i) => i.sku).filter(Boolean);
    const [prods, store] = await Promise.all([
      Product.find({ sku: { $in: skus } }, { sku: 1, category: 1 }).lean(),
      order.storeId ? Store.findById(order.storeId, { type: 1 }).lean() : null,
    ]);
    const catOf = Object.fromEntries(prods.map((p) => [p.sku, p.category]));

    const ts = order.placedAt || new Date();
    await Transaction.create({
      externalId: `order:${order._id}`,
      storeId: order.storeId || null,
      storeType: store?.type,
      userId: order.userId || null,
      ts,
      timeOfDay: timeOfDay(ts.getHours()),
      dayOfWeek: DOW[ts.getDay()],
      dineMode: order.dineMode,
      channel: order.channel || "kiosk",
      lines: order.items.map((i) => ({
        sku: i.sku,
        name_vi: i.name_vi,
        category: catOf[i.sku],
        qty: i.qty,
        unitPrice: i.unitPrice,
      })),
      total: order.totals?.grandTotal ?? 0,
    });
  } catch (e) {
    console.error("[transactions] append failed (non-fatal):", e.message);
  }
}
