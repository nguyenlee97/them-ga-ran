import Product from "../src/models/Product.js";
import AssocRule from "../src/models/AssocRule.js";

/**
 * Curated, menu-grounded association rules (the L1 "backbone" for the demo).
 *
 * We don't have real KFC purchase behaviour, so instead of mining noisy rules
 * from synthetic baskets across 92 items, we generate realistic co-purchase
 * rules from domain knowledge, grounded in the REAL catalog:
 *   main dish  → drink (Pepsi), fries, dessert
 *   combo      → dessert
 *   fries/pop  → drink
 *   trio combo → {main + fries} → drink  (2-item antecedent)
 *
 * Confidence/lift are plausible, deterministic (seeded jitter per sku) so the
 * "…% khách mua cùng" reasons look real. When KFC provides real POS data,
 * `python -m app.mine_rules` REPLACES these with data-mined rules — same schema,
 * nothing downstream changes.
 */

// tiny deterministic hash → 0..1, so numbers are stable across re-seeds
function jitter(sku, spread = 0.06) {
  let h = 0;
  for (const c of sku) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return ((h % 1000) / 1000 - 0.5) * 2 * spread; // ±spread
}
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

export async function seedRules() {
  const products = await Product.find({ available: true }).lean();
  const bySku = Object.fromEntries(products.map((p) => [p.sku, p]));
  const has = (p, t) => (p.tags || []).includes(t);

  // --- pick hero complements (by preferred sku, fallback by tag) ---
  const pickHero = (preferred, tag, extra = () => true) =>
    preferred.map((s) => bySku[s]).find(Boolean) ||
    products.find((p) => has(p, tag) && !p.isCombo && extra(p));

  const heroDrink = pickHero(["pepsi-m", "pepsi-std", "pepsi-vua"], "drink");
  const heroSide = pickHero(["ff-r", "ff-l"], "side", (p) => /khoai tây chiên/i.test(p.name_vi));
  const heroDessert = pickHero(["eggtart-1", "kem-oc-que"], "dessert");
  const heroPopcorn = pickHero(["pop-r", "pop-l"], "side", (p) => /popcorn/i.test(p.name_vi));
  const heroSnack = pickHero(["4-chewy-cheese", "6-chewy-cheese"], "side", (p) => /phô mai viên/i.test(p.name_vi));
  const heroCanDrink = pickHero(["pepsi-can", "7up-can"], "drink", (p) => /lon/i.test(p.name_vi));

  if (!heroDrink || !heroSide) {
    console.warn("[seed:rules] missing hero drink/side — check menu tags");
  }

  // --- classify mains: real food that anchors a meal (not combo/drink/dessert/pure-side) ---
  const isMain = (p) =>
    !p.isCombo && !has(p, "drink") && !has(p, "dessert") &&
    ((has(p, "chicken") && !has(p, "side")) || has(p, "burger") || has(p, "pasta") || has(p, "rice"));
  const mains = products.filter(isMain);
  const combos = products.filter((p) => p.isCombo);

  const rules = [];
  const add = (antecedent, consequent, confidence, lift, context = { timeOfDay: "any", dineMode: "any" }) => {
    if (!consequent || antecedent.includes(consequent) || antecedent.some((a) => !bySku[a]) || !bySku[consequent]) return;
    rules.push({
      antecedent: [...antecedent].sort(), consequent,
      support: clamp(0.03 + confidence * 0.08, 0.01, 0.2),
      confidence: clamp(confidence, 0.05, 0.95),
      lift: clamp(lift, 1.05, 4),
      context,
    });
  };

  // 1) main → drink / fries / dessert
  for (const m of mains) {
    const j = jitter(m.sku);
    const spicy = has(m, "spicy");
    add([m.sku], heroDrink?.sku, (spicy ? 0.66 : 0.58) + j, 2.2 + j * 4);       // chicken → Pepsi
    add([m.sku], heroSide?.sku, 0.42 + j, 1.8 + j * 3);                          // → fries
    add([m.sku], heroDessert?.sku, 0.30 + j, 1.5 + j * 2, { timeOfDay: "afternoon", dineMode: "any" }); // afternoon dessert
    add([m.sku], heroDessert?.sku, 0.14 + j, 1.25 + j, { timeOfDay: "any", dineMode: "any" });          // any-time dessert (weaker)
    // trio: main + fries already in cart → drink (strong)
    if (heroSide) add([m.sku, heroSide.sku], heroDrink?.sku, 0.78 + j, 2.7 + j * 4);
  }

  // 2) combos already bundle a drink + side, so we round out the "meal": a
  //    dessert and a shareable snack; big buckets also get an extra drink + popcorn.
  for (const c of combos) {
    const j = jitter(c.sku);
    add([c.sku], heroDessert?.sku, 0.24 + j, 1.45 + j * 2);      // dessert
    add([c.sku], heroSnack?.sku, 0.18 + j, 1.35 + j);           // cheese balls (snack)
    if (c.price >= 200000) {
      add([c.sku], heroPopcorn?.sku, 0.16 + j, 1.3 + j);        // big party → more to share
      add([c.sku], heroCanDrink?.sku, 0.14 + j, 1.25 + j);      // extra drink for the group
    }
  }

  // 3) sides → drink
  if (heroSide) add([heroSide.sku], heroDrink?.sku, 0.50, 1.9);
  if (heroPopcorn) add([heroPopcorn.sku], heroDrink?.sku, 0.45, 1.8);

  await AssocRule.deleteMany({});
  if (rules.length) await AssocRule.insertMany(rules);
  console.log(`[seed:rules] wrote ${rules.length} curated rules ` +
    `(heroDrink=${heroDrink?.sku}, heroSide=${heroSide?.sku}, heroDessert=${heroDessert?.sku}); ` +
    `${mains.length} mains, ${combos.length} combos`);
  return rules.length;
}
