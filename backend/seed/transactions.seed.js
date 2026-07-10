import Product from "../src/models/Product.js";
import Store from "../src/models/Store.js";
import User from "../src/models/User.js";
import Transaction from "../src/models/Transaction.js";

const rand = (a, b) => Math.floor(Math.random() * (b - a + 1)) + a;
const chance = (p) => Math.random() < p;
const pick = (arr) => arr[rand(0, arr.length - 1)];
const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function timeOfDay(hour) {
  if (hour < 10) return "breakfast";
  if (hour < 14) return "lunch";
  if (hour < 17) return "afternoon";
  if (hour < 21) return "dinner";
  return "late";
}

// Weighted hour sampling — lunch & dinner peaks.
function sampleHour() {
  const buckets = [
    [8, 10, 0.08], [10, 14, 0.34], [14, 17, 0.18], [17, 21, 0.32], [21, 23, 0.08],
  ];
  const r = Math.random();
  let acc = 0;
  for (const [lo, hi, w] of buckets) {
    acc += w;
    if (r <= acc) return rand(lo, hi - 1);
  }
  return 12;
}

/**
 * Build one realistic basket. `groups` = products bucketed by role. The
 * DELIBERATE co-occurrence here (chicken→drink ~68%, fries attach, dessert
 * afternoon-skew, group buckets on weekend dinners) is what makes association
 * rules discover real structure.
 */
function buildBasket(groups, ctx) {
  const lines = [];
  const add = (p, qty = 1) => p && lines.push({ sku: p.sku, name_vi: p.name_vi, category: p.category, qty, unitPrice: p.price });

  const weekend = ctx.dayOfWeek === "Sat" || ctx.dayOfWeek === "Sun";
  const isGroup = (ctx.tod === "dinner" && weekend && chance(0.5)) || chance(0.15);
  const isSnack = ctx.tod === "afternoon" && chance(0.5);

  // 1. Combo occasions — combo is a single line (ordered as a unit).
  if (!isSnack && groups.combo.length && chance(isGroup ? 0.55 : 0.3)) {
    add(pick(groups.combo));
    // A few people still add an extra drink/dessert to a combo.
    if (chance(0.2) && groups.drink.length) add(pick(groups.drink));
    if (ctx.tod === "afternoon" && chance(0.25) && groups.dessert.length) add(pick(groups.dessert));
    return lines;
  }

  // 2. Snack occasion — sides/desserts/drinks, light on mains.
  if (isSnack) {
    if (groups.side.length) add(pick(groups.side));
    if (chance(0.55) && groups.drink.length) add(pick(groups.drink));
    if (chance(0.45) && groups.dessert.length) add(pick(groups.dessert));
    if (chance(0.3) && groups.chicken.length) add(pick(groups.chicken));
    if (!lines.length && groups.drink.length) add(pick(groups.drink));
    return lines;
  }

  // 3. À-la-carte meal: main + attaches.
  const mains = [...groups.chicken, ...groups.burger, ...groups.rice];
  const main = pick(mains.length ? mains : groups.chicken);
  add(main, isGroup ? rand(1, 2) : 1);
  if (isGroup && groups.chicken.length && chance(0.6)) add(pick(groups.chicken), rand(1, 3)); // bucket-y

  // Strong attach signals:
  if (groups.drink.length && chance(isGroup ? 0.85 : 0.68)) add(pick(groups.drink), isGroup ? rand(1, 3) : 1); // chicken→drink
  if (groups.side.length && chance(isGroup ? 0.6 : 0.42)) add(pick(groups.side)); // →fries/side
  const dessertP = ctx.tod === "afternoon" ? 0.32 : 0.12;
  if (groups.dessert.length && chance(dessertP)) add(pick(groups.dessert));

  return lines;
}

export async function seedTransactions(count = 8000) {
  const [products, stores, users] = await Promise.all([
    Product.find().lean(), Store.find().lean(), User.find().lean(),
  ]);
  if (!products.length || !stores.length) throw new Error("Seed menu + stores first.");

  const has = (p, t) => (p.tags || []).includes(t);
  const groups = {
    combo: products.filter((p) => p.isCombo),
    drink: products.filter((p) => has(p, "drink")),
    side: products.filter((p) => has(p, "side")),
    dessert: products.filter((p) => has(p, "dessert")),
    chicken: products.filter((p) => has(p, "chicken")),
    burger: products.filter((p) => has(p, "burger")),
    rice: products.filter((p) => p.category?.includes("Cơm") || p.sku?.includes("com-")),
  };

  await Transaction.deleteMany({});
  const now = Date.now();
  const docs = [];

  for (let i = 0; i < count; i++) {
    const store = pick(stores);
    const daysAgo = rand(0, 270); // ~9 months
    const hour = sampleHour();
    const ts = new Date(now - daysAgo * 864e5);
    ts.setHours(hour, rand(0, 59), 0, 0);
    const ctx = { tod: timeOfDay(hour), dayOfWeek: DOW[ts.getDay()], storeType: store.type };

    const lines = buildBasket(groups, ctx);
    if (!lines.length) continue;
    const total = lines.reduce((s, l) => s + l.unitPrice * l.qty, 0);

    docs.push({
      storeId: store._id,
      storeType: store.type,
      userId: chance(0.4) && users.length ? pick(users)._id : null, // ~40% identified
      ts,
      timeOfDay: ctx.tod,
      dayOfWeek: ctx.dayOfWeek,
      dineMode: chance(0.55) ? "dine_in" : "takeaway",
      channel: "kiosk",
      lines,
      total,
    });
  }

  // Bulk insert in chunks.
  const CHUNK = 1000;
  for (let i = 0; i < docs.length; i += CHUNK) {
    await Transaction.insertMany(docs.slice(i, i + CHUNK));
  }
  console.log(`[seed:transactions] inserted ${docs.length} synthetic POS transactions`);
  return docs.length;
}
