import User from "../src/models/User.js";

const NAMES = ["Minh", "Lan", "Huy", "Trang", "Nam", "Thu", "Phong", "Vy", "Khoa", "Ngân",
  "Đạt", "Hà", "Sơn", "Mai", "Tú", "Linh", "Bảo", "Quyên", "Hải", "Chi"];

function rand(a, b) { return Math.floor(Math.random() * (b - a + 1)) + a; }
function pick(arr) { return arr[rand(0, arr.length - 1)]; }

/**
 * Synthetic members with varied RFM so personalization has signal.
 * count members; ~15% gold, ~5% platinum.
 */
export async function seedUsers(count = 60) {
  await User.deleteMany({});
  const docs = [];
  for (let i = 0; i < count; i++) {
    const roll = Math.random();
    const tier = roll > 0.95 ? "platinum" : roll > 0.8 ? "gold" : "member";
    const totalOrders = rand(1, 40);
    const avg = rand(60000, 220000);
    docs.push({
      phone: `09${rand(10000000, 99999999)}`,
      name: `${pick(NAMES)} ${pick(["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng"])}`,
      tier,
      pointsBalance: rand(0, 5000),
      stats: {
        visitCount: totalOrders,
        totalOrders,
        totalSpend: totalOrders * avg,
        firstOrderAt: new Date(Date.now() - rand(120, 400) * 864e5),
        lastOrderAt: new Date(Date.now() - rand(0, 30) * 864e5),
      },
    });
  }
  const inserted = await User.insertMany(docs);
  console.log(`[seed:users] inserted ${inserted.length} members`);
  return inserted;
}
