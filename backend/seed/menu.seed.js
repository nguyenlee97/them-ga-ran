import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import Product from "../src/models/Product.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Prefer freshly scraped menu.json; fall back to the curated sample.
async function loadMenu() {
  const scraped = path.resolve(__dirname, "../../scraper/menu.json");
  const sample = path.resolve(__dirname, "../../scraper/menu.sample.json");
  for (const f of [scraped, sample]) {
    try {
      const raw = await readFile(f, "utf8");
      const items = JSON.parse(raw);
      if (Array.isArray(items) && items.length) {
        console.log(`[seed:menu] using ${path.basename(f)} (${items.length} items)`);
        return items;
      }
    } catch { /* try next */ }
  }
  throw new Error("No menu source found (scraper/menu.json or menu.sample.json).");
}

export async function seedMenu() {
  const items = await loadMenu();
  await Product.deleteMany({});
  const docs = items.map((it, i) => ({
    sku: it.sku,
    name_vi: it.name_vi || it.name,
    name_en: it.name_en || "",
    category: it.category || "KFC",
    price: it.price || 0,
    oldPrice: it.oldPrice || null,
    code: it.code || it.sku,
    imageUrl: it.imageUrl || "",
    description: it.description || "",
    tags: it.tags || [],
    isCombo: !!it.isCombo,
    available: it.available !== false,
    sortOrder: i,
  }));
  await Product.insertMany(docs);
  console.log(`[seed:menu] inserted ${docs.length} products`);
  return docs;
}
