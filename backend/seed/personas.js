/**
 * Persona-based synthetic member behavior.
 *
 * The organizers provide NO data, so synthetic data is the permanent
 * substrate. Random per-transaction user assignment gives every member an
 * incoherent grab-bag history — personalization over that is noise. Instead,
 * each member gets a persona (taste + time-of-day + weekend + dine-mode bias)
 * and fixed favorite items, and their history is generated FROM that persona.
 * Result: recency-weighted affinity has real signal and logged-in demos show
 * visibly different recommendations per member.
 */

const rand = (a, b) => Math.floor(Math.random() * (b - a + 1)) + a;
const chance = (p) => Math.random() < p;
const pick = (arr) => (arr && arr.length ? arr[rand(0, arr.length - 1)] : null);

/** Hour ranges per time-of-day bucket (matches timeOfDay() in transactions.seed). */
export const TOD_HOURS = {
  breakfast: [8, 9],
  lunch: [10, 13],
  afternoon: [14, 16],
  dinner: [17, 20],
  late: [21, 22],
};

/** Bucket the menu by role. Complements exclude combos (combos are units). */
export function buildGroups(products) {
  const has = (p, t) => (p.tags || []).includes(t);
  const cat = (p) => p.category || "";
  return {
    combo: products.filter((p) => p.isCombo),
    comboSolo: products.filter((p) => p.isCombo && cat(p).includes("1 Người")),
    comboGroup: products.filter((p) => p.isCombo && (cat(p).includes("Nhóm") || p.price >= 200000)),
    drink: products.filter((p) => has(p, "drink") && !p.isCombo && !has(p, "chicken")),
    side: products.filter((p) => has(p, "side") && !p.isCombo),
    dessert: products.filter((p) => has(p, "dessert") && !p.isCombo),
    chicken: products.filter((p) => has(p, "chicken") && !p.isCombo),
    burger: products.filter((p) => has(p, "burger") && !p.isCombo),
    rice: products.filter((p) => cat(p).includes("Cơm") || (p.sku || "").includes("com-")),
    light: products.filter((p) => cat(p).includes("Xanh")),
  };
}

/**
 * Personas. Each defines:
 * - weight: share of the member base
 * - tods: time-of-day visit distribution
 * - weekendBias: probability a visit is snapped to Sat/Sun
 * - dineIn: probability of dine_in
 * - favoriteRoles: [group, count] pairs — fixed favorites picked once per user
 * - build(groups, fav, ctx): one visit's basket. `fav(pool)` returns the
 *   user's favorite within that pool ~75% of the time (else explores).
 */
export const PERSONAS = {
  ga_ran_classic: {
    label: "Fan gà rán truyền thống",
    weight: 0.24,
    tods: { lunch: 0.35, dinner: 0.45, afternoon: 0.1, late: 0.1 },
    weekendBias: 0.35,
    dineIn: 0.65,
    favoriteRoles: [["chicken", 1], ["drink", 1], ["side", 1]],
    build(g, fav, ctx, add) {
      add(fav(g.chicken), chance(0.3) ? 2 : 1);
      if (chance(0.85)) add(fav(g.drink));
      if (chance(0.55)) add(fav(g.side));
      if (chance(ctx.tod === "afternoon" ? 0.35 : 0.12)) add(pick(g.dessert));
    },
  },
  burger_lunch: {
    label: "Burger giờ trưa văn phòng",
    weight: 0.16,
    tods: { lunch: 0.6, dinner: 0.25, afternoon: 0.15 },
    weekendBias: 0.15,
    dineIn: 0.35,
    favoriteRoles: [["burger", 1], ["drink", 1]],
    build(g, fav, ctx, add) {
      add(fav(g.burger));
      if (chance(0.7)) add(fav(g.drink));
      if (chance(0.35)) add(pick(g.side));
      if (chance(0.08)) add(pick(g.dessert));
    },
  },
  family_weekend: {
    label: "Gia đình cuối tuần",
    weight: 0.16,
    tods: { dinner: 0.75, lunch: 0.2, afternoon: 0.05 },
    weekendBias: 0.75,
    dineIn: 0.8,
    favoriteRoles: [["comboGroup", 1], ["drink", 1], ["dessert", 1]],
    build(g, fav, ctx, add) {
      const bucket = fav(g.comboGroup.length ? g.comboGroup : g.combo);
      if (bucket) add(bucket);
      else add(pick(g.chicken), rand(3, 6)); // no group combos on menu → bucket of pieces
      if (chance(0.6)) add(fav(g.drink), rand(2, 3));
      if (chance(0.4)) add(fav(g.dessert), rand(1, 2));
      if (chance(0.3)) add(pick(g.side));
    },
  },
  trang_mieng: {
    label: "Tín đồ tráng miệng xế chiều",
    weight: 0.14,
    tods: { afternoon: 0.65, late: 0.2, lunch: 0.15 },
    weekendBias: 0.3,
    dineIn: 0.5,
    favoriteRoles: [["dessert", 2], ["drink", 1], ["side", 1]],
    build(g, fav, ctx, add) {
      add(fav(g.dessert));
      if (chance(0.35)) add(pick(g.dessert));
      if (chance(0.6)) add(fav(g.drink));
      if (chance(0.4)) add(fav(g.side));
      if (chance(0.15)) add(pick(g.chicken));
    },
  },
  combo_solo: {
    label: "Combo 1 người tiện lợi",
    weight: 0.18,
    tods: { lunch: 0.55, dinner: 0.35, late: 0.1 },
    weekendBias: 0.15,
    dineIn: 0.5,
    favoriteRoles: [["comboSolo", 1], ["drink", 1]],
    build(g, fav, ctx, add) {
      add(fav(g.comboSolo.length ? g.comboSolo : g.combo));
      if (chance(0.25)) add(fav(g.drink)); // combo already has a drink; some add extra
      if (chance(ctx.tod === "afternoon" ? 0.2 : 0.1)) add(pick(g.dessert));
    },
  },
  an_nhe: {
    label: "Ăn nhẹ thanh đạm",
    weight: 0.12,
    tods: { lunch: 0.5, dinner: 0.4, afternoon: 0.1 },
    weekendBias: 0.25,
    dineIn: 0.6,
    favoriteRoles: [["light", 1], ["rice", 1], ["drink", 1]],
    build(g, fav, ctx, add) {
      add(fav(g.light.length ? g.light : g.rice));
      if (chance(0.55)) add(fav(g.drink));
      if (chance(0.2)) add(pick(g.side));
      if (chance(0.08)) add(pick(g.dessert));
    },
  },
};

/** Weighted persona sample. */
export function samplePersona() {
  const entries = Object.entries(PERSONAS);
  const r = Math.random();
  let acc = 0;
  for (const [key, p] of entries) {
    acc += p.weight;
    if (r <= acc) return key;
  }
  return entries[entries.length - 1][0];
}

/**
 * Scripted demo accounts — known phones (any login code works), strong
 * distinct personas, "regular" cadence so their histories are rich & recent.
 * Log in as each on the kiosk to show visibly different recommendations.
 */
export const DEMO_ACCOUNTS = [
  { phone: "0900000001", name: "An Gà Rán", persona: "ga_ran_classic" },
  { phone: "0900000002", name: "Bích Tráng Miệng", persona: "trang_mieng" },
  { phone: "0900000003", name: "Cường Gia Đình", persona: "family_weekend" },
];

export const DEMO_PHONES = new Set(DEMO_ACCOUNTS.map((d) => d.phone));

/** Pick fixed favorite skus for a user of the given persona. */
export function pickFavorites(personaKey, groups) {
  const persona = PERSONAS[personaKey];
  const favs = [];
  for (const [role, n] of persona.favoriteRoles) {
    const pool = groups[role] || [];
    const chosen = new Set();
    for (let i = 0; i < n && chosen.size < pool.length; i++) {
      let p = pick(pool);
      let guard = 0;
      while (p && chosen.has(p.sku) && guard++ < 10) p = pick(pool);
      if (p && !chosen.has(p.sku)) {
        chosen.add(p.sku);
        favs.push(p.sku);
      }
    }
  }
  return favs;
}
