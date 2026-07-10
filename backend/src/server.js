import "dotenv/config";
import express from "express";
import cors from "cors";
import morgan from "morgan";

import { connectDB } from "./db.js";
import { notFound, errorHandler } from "./middleware/error.js";

import menuRoutes from "./routes/menu.js";
import storeRoutes from "./routes/stores.js";
import authRoutes from "./routes/auth.js";
import cartRoutes from "./routes/carts.js";
import orderRoutes from "./routes/orders.js";
import loyaltyRoutes from "./routes/loyalty.js";
import voucherRoutes from "./routes/vouchers.js";
import recommendRoutes from "./routes/recommend.js";
import eventRoutes from "./routes/events.js";
import handoffRoutes from "./routes/handoff.js";
import adminRoutes from "./routes/admin.js";

const app = express();

const origins = (process.env.CORS_ORIGINS || "*").split(",").map((s) => s.trim());
app.use(cors({ origin: origins.includes("*") ? true : origins }));
app.use(express.json({ limit: "1mb" }));
app.use(morgan("dev"));

app.get("/health", (req, res) => res.json({ ok: true, service: "kfc-backend", ts: Date.now() }));

app.use("/api/menu", menuRoutes);
app.use("/api/stores", storeRoutes);
app.use("/api/auth", authRoutes);
app.use("/api/carts", cartRoutes);
app.use("/api/orders", orderRoutes);
app.use("/api/loyalty", loyaltyRoutes);
app.use("/api/vouchers", voucherRoutes);
app.use("/api/recommend", recommendRoutes);
app.use("/api/events", eventRoutes);
app.use("/api/handoff", handoffRoutes);
app.use("/api/admin", adminRoutes);

app.use(notFound);
app.use(errorHandler);

const PORT = process.env.PORT || 3000;

connectDB()
  .then(() => {
    app.listen(PORT, () => console.log(`[kfc-backend] listening on :${PORT}`));
  })
  .catch((err) => {
    console.error("[kfc-backend] failed to start:", err.message);
    process.exit(1);
  });

export default app;
