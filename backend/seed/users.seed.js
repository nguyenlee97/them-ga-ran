import User from "../src/models/User.js";
import Product from "../src/models/Product.js";
import { buildGroups, samplePersona, pickFavorites, DEMO_ACCOUNTS } from "./personas.js";

const NAMES = ["Minh", "Lan", "Huy", "Trang", "Nam", "Thu", "Phong", "Vy", "Khoa", "Ngân",
  "Đạt", "Hà", "Sơn", "Mai", "Tú", "Linh", "Bảo", "Quyên", "Hải", "Chi"];
const SURNAMES = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng"];

function rand(a, b) { return Math.floor(Math.random() * (b - a + 1)) + a; }
function pick(arr) { return arr[rand(0, arr.length - 1)]; }

/**
 * Persona-based synthetic members. Each user gets a persona + fixed favorite
 * items; transactions.seed.js generates their purchase history FROM that
 * persona, then recomputes stats/tier/points from the actual history.
 * Includes 3 named demo accounts with known phones (see personas.js).
 */
export async function seedUsers(count = 60) {
  const products = await Product.find().lean();
  if (!products.length) throw new Error("Seed menu first.");
  const groups = buildGroups(products);

  await User.deleteMany({});
  const docs = [];
  const phones = new Set();

  // Scripted demo accounts first.
  for (const d of DEMO_ACCOUNTS) {
    phones.add(d.phone);
    docs.push({
      phone: d.phone,
      name: d.name,
      persona: d.persona,
      favorites: pickFavorites(d.persona, groups),
      tier: "member", // recomputed from generated spend in transactions.seed
      pointsBalance: 0,
      stats: {},
    });
  }

  for (let i = 0; i < count; i++) {
    let phone = `09${rand(10000000, 99999999)}`;
    while (phones.has(phone)) phone = `09${rand(10000000, 99999999)}`;
    phones.add(phone);
    const persona = samplePersona();
    docs.push({
      phone,
      name: `${pick(NAMES)} ${pick(SURNAMES)}`,
      persona,
      favorites: pickFavorites(persona, groups),
      tier: "member",
      pointsBalance: 0,
      stats: {},
    });
  }

  const inserted = await User.insertMany(docs);
  console.log(`[seed:users] inserted ${inserted.length} members (${DEMO_ACCOUNTS.length} demo accounts, persona-based)`);
  return inserted;
}
