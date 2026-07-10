/**
 * KFC Vietnam menu scraper — verified against the live site (kfcvietnam.com.vn/menu).
 *
 * Loads the menu, waits for hydration, then extracts every product with its
 * real category, price, old price, description, and REAL image URL
 * (https://static.kfcvietnam.com.vn/images/items/lg/<CODE>.jpg). Output is
 * written to ./menu.json in the backend Product shape; the seed loads it.
 *
 * Extraction strategy (proven):
 *   - Category headers are the section titles (matched case-insensitively —
 *     they're title-case in the DOM, uppercased via CSS).
 *   - Product images are <img> whose src contains "/images/items/".
 *   - Each card is the nearest ancestor of the img whose text contains "₫".
 *
 * Usage:
 *   npm install && npx playwright install chromium
 *   node scrape_menu.js            # writes menu.json
 *   node scrape_menu.js --headful  # watch it run
 */
import { chromium } from "playwright";
import { writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const URL = "https://www.kfcvietnam.com.vn/menu/hot-deal";

async function autoScroll(page) {
  await page.evaluate(async () => {
    await new Promise((res) => {
      let y = 0; const step = 700;
      const t = setInterval(() => {
        window.scrollBy(0, step); y += step;
        if (y >= document.body.scrollHeight) { clearInterval(t); res(); }
      }, 150);
    });
  });
  await page.waitForTimeout(800);
}

async function scrape({ headful = false } = {}) {
  const browser = await chromium.launch({ headless: !headful });
  const page = await browser.newPage({ locale: "vi-VN" });
  await page.goto(URL, { waitUntil: "networkidle", timeout: 60000 });
  await page.waitForTimeout(2500);
  await autoScroll(page);

  const items = await page.evaluate(() => {
    const CATS = ["ƯU ĐÃI", "MÓN MỚI", "COMBO 1 NGƯỜI", "COMBO NHÓM",
      "GÀ RÁN - GÀ QUAY", "BURGER - CƠM - MÌ Ý", "THỨC ĂN NHẸ", "THỨC UỐNG & TRÁNG MIỆNG"];
    const CATMAP = {
      "ƯU ĐÃI": "Ưu Đãi", "MÓN MỚI": "Món Mới", "COMBO 1 NGƯỜI": "Combo 1 Người",
      "COMBO NHÓM": "Combo Nhóm", "GÀ RÁN - GÀ QUAY": "Gà Rán - Gà Quay",
      "BURGER - CƠM - MÌ Ý": "Burger - Cơm - Mì Ý", "THỨC ĂN NHẸ": "Thức Ăn Nhẹ",
      "THỨC UỐNG & TRÁNG MIỆNG": "Thức Uống & Tráng Miệng" };
    const norm = (s) => (s || "").trim().toUpperCase();
    const tagize = (name, catU, desc) => {
      const s = (name + " " + desc).toLowerCase(); const t = [];  // name+desc only, NOT category
      if (/combo|xô|bucket/.test(s)) t.push("combo");
      if (/pepsi|7up|lipton|nước|trà/.test(s)) t.push("drink");
      if (/bánh trứng|\bkem\b|sundae|ốc quế|tráng miệng/.test(s)) t.push("dessert");
      if (/khoai|salad|phô mai viên|bắp cải|súp|cơm trắng|popcorn|nghiền/.test(s)) t.push("side");
      if (/gà rán|miếng gà|tender|popcorn|phi-lê|gà lắc|xốt mắm|gà quay|gà viên|nanban/.test(s)) t.push("chicken");
      if (/burger/.test(s)) t.push("burger");
      if (/mì ý/.test(s)) t.push("pasta");
      if (/\bcơm\b/.test(s)) t.push("rice");
      if (/lắc tiêu|zinger|\bcay\b|xốt mắm/.test(s)) t.push("spicy");
      if (catU === "MÓN MỚI") t.push("new");
      if (catU === "ƯU ĐÃI") t.push("deal", "bestseller");
      return [...new Set(t)];
    };

    const out = []; const seen = new Set(); let curU = "";
    for (const el of document.querySelectorAll("*")) {
      if (el.childElementCount === 0 && CATS.includes(norm(el.textContent))) { curU = norm(el.textContent); continue; }
      if (el.tagName === "IMG" && /\/images\/items\//.test(el.currentSrc || el.src || "")) {
        let p = el, card = null;
        for (let k = 0; k < 6 && p; k++) { p = p.parentElement; if (p && /₫/.test(p.textContent)) { card = p; break; } }
        if (!card) continue;
        const src = (el.currentSrc || el.src).split("?")[0];
        const code = src.split("/").pop().replace(/\.(jpg|jpeg|png|webp)$/i, "");
        if (seen.has(code)) continue; seen.add(code);
        const lines = card.innerText.split("\n").map((s) => s.trim()).filter(Boolean).filter((s) => s !== "i" && s !== "Thêm");
        const prices = lines.filter((s) => /₫/.test(s)).map((s) => parseInt(s.replace(/[^\d]/g, ""), 10)).filter(Boolean);
        const nonPrice = lines.filter((s) => !/₫/.test(s));
        const name = nonPrice[0] || "";
        const desc = nonPrice.slice(1).sort((a, b) => b.length - a.length)[0] || "";
        let sku = code.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
        while (out.find((o) => o.sku === sku)) sku += "-x";
        out.push({
          sku, code, name_vi: name, name_en: "",
          category: CATMAP[curU] || curU || "KFC",
          price: prices.length ? Math.min(...prices) : 0,
          oldPrice: prices.length > 1 ? Math.max(...prices) : null,
          imageUrl: src, description: desc,
          tags: tagize(name, curU, desc),
          isCombo: /combo|xô|bucket/i.test(name),
        });
      }
    }
    return out;
  });

  await browser.close();
  return items;
}

const headful = process.argv.includes("--headful");
scrape({ headful })
  .then(async (products) => {
    const outPath = path.join(__dirname, "menu.json");
    await writeFile(outPath, JSON.stringify(products, null, 2), "utf8");
    console.log(`[scraper] wrote ${products.length} products → ${outPath}`);
    if (!products.length) console.warn("[scraper] 0 items — the KFC DOM may have changed; seed will fall back to menu.sample.json.");
  })
  .catch((e) => { console.error("[scraper] failed:", e.message); process.exit(1); });
