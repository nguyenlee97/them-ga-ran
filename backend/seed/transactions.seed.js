import Product from "../src/models/Product.js";
import Store from "../src/models/Store.js";
import User from "../src/models/User.js";
import Transaction from "../src/models/Transaction.js";
import { buildGroups, PERSONAS, TOD_HOURS, DEMO_PHONES } from "./personas.js";

const rand = (a, b) => Math.floor(Math.random() * (b - a + 1)) + a;
const chance = (p) => Math.random() < p;
const pick = (arr) => (arr && arr.length ? arr[rand(0, arr.length - 1)] : null);
const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function timeOfDay(hour) {
  if (hour < 10) return "breakfast";
  if (hour < 14) return "lunch";
  if (hour < 17) return "afternoon";
  if (hour < 21) return "dinner";
  return "late";
}

// Weighted hour sampling for ANONYMOUS traffic — lunch & dinner peaks.
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

/** Sample a time-of-day bucket from a persona's distribution. */
function sampleTod(weights) {
  const r = Math.random();
  let acc = 0;
  for (const [tod, w] of Object.entries(weights)) {
    acc += w;
    if (r <= acc) return tod;
  }
  return Object.keys(weights)[0];
}

/**
 * Visit cadences — how often & how recently a member visits over ~9 months.
 * `lastGap` = days since their most recent visit (lapsed members stopped).
 */
const CADENCES = [
  ["regular", 0.35, () => ({ visits: rand(26, 42), startAgo: 270, lastGap: rand(0, 7) })],
  ["occasional", 0.35, () => ({ visits: rand(9, 16), startAgo: 270, lastGap: rand(3, 21) })],
  ["lapsed", 0.20, () => ({ visits: rand(6, 14), startAgo: 270, lastGap: rand(60, 150) })],
  ["new_member", 0.10, () => ({ visits: rand(3, 6), startAgo: 21, lastGap: rand(0, 5) })],
];

function sampleCadence(isDemo) {
  if (isDemo) return CADENCES[0][2](); // demo accounts: rich, recent history
  const r = Math.random();
  let acc = 0;
  for (const [, w, fn] of CADENCES) {
    acc += w;
    if (r <= acc) return fn();
  }
  return CADENCES[1][2]();
}

/** Evenly-spread visit day offsets (days ago) with jitter. */
function visitDays({ visits, startAgo, lastGap }) {
  const span = Math.max(1, startAgo - lastGap);
  const days = [];
  for (let i = 0; i < visits; i++) {
    const d = Math.round(lastGap + (span * i) / visits + rand(-3, 3));
    days.push(Math.min(startAgo, Math.max(lastGap, d)));
  }
  return days;
}

/** Snap a timestamp to the nearest weekend day (for weekend-biased personas). */
function snapWeekend(ts) {
  for (const off of [0, 1, -1, 2, -2, 3, -3]) {
    const d = new Date(ts.getTime() + off * 864e5);
    const dow = d.getDay();
    if (dow === 0 || dow === 6) return d;
  }
  return ts;
}

/**
 * One ANONYMOUS basket (no persona). The DELIBERATE co-occurrence here
 * (chicken→drink ~68%, fries attach, dessert afternoon-skew, group buckets on
 * weekend dinners) is what makes association rules discover real structure.
 */
function buildAnonBasket(groups, ctx) {
  const lines = [];
  const add = (p, qty = 1) => p && lines.push({ sku: p.sku, name_vi: p.name_vi, category: p.category, qty, unitPrice: p.price });

  const weekend = ctx.dayOfWeek === "Sat" || ctx.dayOfWeek === "Sun";
  const isGroup = (ctx.tod === "dinner" && weekend && chance(0.5)) || chance(0.15);
  const isSnack = ctx.tod === "afternoon" && chance(0.5);

  if (!isSnack && groups.combo.length && chance(isGroup ? 0.55 : 0.3)) {
    add(pick(groups.combo));
    if (chance(0.2) && groups.drink.length) add(pick(groups.drink));
    if (ctx.tod === "afternoon" && chance(0.25) && groups.dessert.length) add(pick(groups.dessert));
    return lines;
  }

  if (isSnack) {
    if (groups.side.length) add(pick(groups.side));
    if (chance(0.55) && groups.drink.length) add(pick(groups.drink));
    if (chance(0.45) && groups.dessert.length) add(pick(groups.dessert));
    if (chance(0.3) && groups.chicken.length) add(pick(groups.chicken));
    if (!lines.length && groups.drink.length) add(pick(groups.drink));
    return lines;
  }

  const mains = [...groups.chicken, ...groups.burger, ...groups.rice];
  const main = pick(mains.length ? mains : groups.chicken);
  add(main, isGroup ? rand(1, 2) : 1);
  if (isGroup && groups.chicken.length && chance(0.6)) add(pick(groups.chicken), rand(1, 3));

  if (groups.drink.length && chance(isGroup ? 0.85 : 0.68)) add(pick(groups.drink), isGroup ? rand(1, 3) : 1);
  if (groups.side.length && chance(isGroup ? 0.6 : 0.42)) add(pick(groups.side));
  const dessertP = ctx.tod === "afternoon" ? 0.32 : 0.12;
  if (groups.dessert.length && chance(dessertP)) add(pick(groups.dessert));

  return lines;
}

/**
 * Synthetic POS history, persona-aware:
 *  1. Every member gets a coherent history generated from their persona +
 *     fixed favorites + a visit cadence (regular / occasional / lapsed / new).
 *  2. The remainder up to `count` is anonymous traffic with the same
 *     deliberate co-occurrence structure (fuel for association-rule mining).
 *  3. Member stats/tier/points are recomputed from the ACTUAL generated
 *     history so loyalty numbers and reco personalization agree.
 */
export async function seedTransactions(count = 8000) {
  const [products, stores, users] = await Promise.all([
    Product.find().lean(), Store.find().lean(), User.find().lean(),
  ]);
  if (!products.length || !stores.length) throw new Error("Seed menu + stores first.");

  const groups = buildGroups(products);
  const bySku = Object.fromEntries(products.map((p) => [p.sku, p]));

  await Transaction.deleteMany({});
  const now = Date.now();
  const docs = [];

  // ---- 1) Identified persona histories -------------------------------------
  for (const user of users) {
    const persona = PERSONAS[user.persona] || PERSONAS.ga_ran_classic;
    const cadence = sampleCadence(DEMO_PHONES.has(user.phone));
    const homeStore = pick(stores);
    const favProds = (user.favorites || []).map((s) => bySku[s]).filter(Boolean);
    const favSkus = new Set(favProds.map((p) => p.sku));

    // Favorite-within-pool: ~75% loyal to the favorite, else explore.
    const fav = (pool) => {
      if (!pool || !pool.length) return null;
      const mine = pool.filter((p) => favSkus.has(p.sku));
      return mine.length && chance(0.75) ? pick(mine) : pick(pool);
    };

    for (const daysAgo of visitDays(cadence)) {
      const tod = sampleTod(persona.tods);
      const [lo, hi] = TOD_HOURS[tod] || TOD_HOURS.lunch;
      let ts = new Date(now - daysAgo * 864e5);
      if (chance(persona.weekendBias)) ts = snapWeekend(ts);
      ts.setHours(rand(lo, hi), rand(0, 59), 0, 0);

      const ctx = { tod, dayOfWeek: DOW[ts.getDay()] };
      const lines = [];
      const add = (p, qty = 1) => p && lines.push({ sku: p.sku, name_vi: p.name_vi, category: p.category, qty, unitPrice: p.price });
      persona.build(groups, fav, ctx, add);
      if (!lines.length) continue;

      const store = chance(0.85) ? homeStore : pick(stores);
      docs.push({
        storeId: store._id,
        storeType: store.type,
        userId: user._id,
        ts,
        timeOfDay: ctx.tod,
        dayOfWeek: ctx.dayOfWeek,
        dineMode: chance(persona.dineIn) ? "dine_in" : "takeaway",
        channel: "kiosk",
        lines,
        total: lines.reduce((s, l) => s + l.unitPrice * l.qty, 0),
      });
    }
  }
  const identified = docs.length;

  // ---- 2) Anonymous fill ----------------------------------------------------
  const anonTarget = Math.max(0, count - identified);
  for (let i = 0; i < anonTarget; i++) {
    const store = pick(stores);
    const daysAgo = rand(0, 270);
    const hour = sampleHour();
    const ts = new Date(now - daysAgo * 864e5);
    ts.setHours(hour, rand(0, 59), 0, 0);
    const ctx = { tod: timeOfDay(hour), dayOfWeek: DOW[ts.getDay()] };

    const lines = buildAnonBasket(groups, ctx);
    if (!lines.length) continue;

    docs.push({
      storeId: store._id,
      storeType: store.type,
      userId: null,
      ts,
      timeOfDay: ctx.tod,
      dayOfWeek: ctx.dayOfWeek,
      dineMode: chance(0.55) ? "dine_in" : "takeaway",
      channel: "kiosk",
      lines,
      total: lines.reduce((s, l) => s + l.unitPrice * l.qty, 0),
    });
  }

  const CHUNK = 1000;
  for (let i = 0; i < docs.length; i += CHUNK) {
    await Transaction.insertMany(docs.slice(i, i + CHUNK));
  }
  console.log(`[seed:transactions] inserted ${docs.length} transactions (${identified} identified persona visits, ${docs.length - identified} anonymous)`);

  // ---- 3) Recompute member stats/tier/points from actual history ------------
  const perUser = new Map();
  for (const d of docs) {
    if (!d.userId) continue;
    const k = String(d.userId);
    const agg = perUser.get(k) || { visits: 0, spend: 0, first: d.ts, last: d.ts };
    agg.visits += 1;
    agg.spend += d.total;
    if (d.ts < agg.first) agg.first = d.ts;
    if (d.ts > agg.last) agg.last = d.ts;
    perUser.set(k, agg);
  }

  const TIER_RATES = { member: 0.03, gold: 0.05, platinum: 0.07 };
  const ops = [];
  for (const [userId, a] of perUser) {
    const tier = a.spend >= 8_000_000 ? "platinum" : a.spend >= 3_500_000 ? "gold" : "member";
    ops.push({
      updateOne: {
        filter: { _id: userId },
        update: {
          $set: {
            tier,
            pointsBalance: Math.round(a.spend * TIER_RATES[tier] * (0.2 + Math.random() * 0.8)),
            stats: {
              visitCount: a.visits,
              totalOrders: a.visits,
              totalSpend: a.spend,
              firstOrderAt: a.first,
              lastOrderAt: a.last,
            },
          },
        },
      },
    });
  }
  if (ops.length) await User.bulkWrite(ops);
  console.log(`[seed:transactions] recomputed stats/tier/points for ${ops.length} members`);

  return docs.length;
}
