import "dotenv/config";
import { connectDB } from "../src/db.js";
import mongoose from "../src/db.js";
import { seedMenu } from "./menu.seed.js";
import { seedStores } from "./stores.seed.js";
import { seedUsers } from "./users.seed.js";
import { seedVouchers } from "./vouchers.seed.js";
import { seedTransactions } from "./transactions.seed.js";
import { seedRules } from "./rules.seed.js";

async function main() {
  await connectDB();
  console.log("=== KFC seed start ===");
  await seedMenu();
  await seedStores();
  await seedUsers(60);
  await seedVouchers();
  await seedTransactions(Number(process.env.SEED_TX_COUNT) || 8000);
  await seedRules();
  console.log("=== KFC seed done ===");
  await mongoose.connection.close();
  process.exit(0);
}

main().catch((e) => {
  console.error("[seed] failed:", e);
  process.exit(1);
});
