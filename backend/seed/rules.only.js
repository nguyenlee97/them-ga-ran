import "dotenv/config";
import { connectDB } from "../src/db.js";
import mongoose from "../src/db.js";
import { seedRules } from "./rules.seed.js";

const run = async () => {
  await connectDB();
  await seedRules();
  await mongoose.connection.close();
  process.exit(0);
};
run().catch((e) => { console.error("[seed:rules] failed:", e); process.exit(1); });
