/**
 * Zero-build metrics dashboard, served at GET /api/admin/dashboard.
 * Vanilla HTML/JS over /api/admin/metrics — auto-refreshes every 10s.
 * The demo money-shot: AOV uplift of orders with vs without accepted recs.
 */
export const DASHBOARD_HTML = `<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KFC Reco Metrics</title>
<style>
  :root { --red: #e4002b; --dark: #1f1f1f; }
  * { box-sizing: border-box; margin: 0; }
  body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; background: #f6f6f6; color: var(--dark); padding: 24px; }
  header { display: flex; align-items: baseline; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }
  h1 { font-size: 22px; } h1 span { color: var(--red); }
  .win { margin-left: auto; display: flex; gap: 6px; }
  .win button { border: 1px solid #ddd; background: #fff; border-radius: 8px; padding: 6px 12px; cursor: pointer; font-weight: 600; }
  .win button.on { background: var(--red); color: #fff; border-color: var(--red); }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 20px; }
  .card { background: #fff; border-radius: 14px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,.07); }
  .card .k { font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: .04em; }
  .card .v { font-size: 26px; font-weight: 800; margin-top: 4px; }
  .card .v.red { color: var(--red); }
  .card .sub { font-size: 12px; color: #999; margin-top: 2px; }
  .grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 12px; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #eee; }
  th { font-size: 11px; color: #888; text-transform: uppercase; }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
  .bar { height: 6px; background: #f0f0f0; border-radius: 3px; overflow: hidden; margin-top: 3px; }
  .bar i { display: block; height: 100%; background: var(--red); }
  .muted { color: #aaa; font-size: 13px; }
  h2 { font-size: 15px; margin-bottom: 10px; }
  #err { color: var(--red); font-weight: 600; display: none; margin-bottom: 12px; }
</style>
</head>
<body>
<header>
  <h1><span>KFC</span> Recommendation Metrics</h1>
  <span class="muted" id="upd"></span>
  <div class="win">
    <button data-d="1">24h</button>
    <button data-d="7">7 ngày</button>
    <button data-d="0" class="on">Tất cả</button>
  </div>
</header>
<div id="err"></div>
<div class="cards" id="cards"></div>
<div class="grid2">
  <div class="card"><h2>Theo vị trí (slot)</h2><table id="slots"></table></div>
  <div class="card"><h2>Chấp nhận theo chiến lược</h2><table id="strats"></table></div>
  <div class="card"><h2>Nâng cấp Combo</h2><table id="combo"></table></div>
  <div class="card"><h2>AOV — có vs không có gợi ý được chấp nhận</h2><table id="aov"></table></div>
</div>
<script>
let days = 0;
const vnd = (n) => (n == null ? "—" : Number(n).toLocaleString("vi-VN") + " ₫");
const pct = (x, d = 1) => (x == null ? "—" : (x * 100).toFixed(d) + "%");

function card(k, v, sub, red) {
  return '<div class="card"><div class="k">' + k + '</div><div class="v' + (red ? " red" : "") + '">' + v + '</div>' +
    (sub ? '<div class="sub">' + sub + "</div>" : "") + "</div>";
}
function rows(el, head, body) {
  document.getElementById(el).innerHTML = "<tr>" + head.map((h, i) => "<th" + (i ? ' class=num' : "") + ">" + h + "</th>").join("") + "</tr>" +
    (body.length ? body.join("") : '<tr><td colspan="9" class="muted">Chưa có dữ liệu</td></tr>');
}

async function load() {
  try {
    const m = await (await fetch("/api/admin/metrics?days=" + days)).json();
    document.getElementById("err").style.display = "none";

    const up = m.aov.upliftPct;
    document.getElementById("cards").innerHTML =
      card("Gợi ý đã hiển thị", m.funnel.itemImpressions, m.funnel.responses + " lần gọi /recommend") +
      card("Đã chấp nhận", m.funnel.accepted, "tỉ lệ " + pct(m.funnel.acceptanceRate)) +
      card("Doanh thu từ gợi ý", vnd(m.revenue.acceptedRecRevenue), "món thêm do AI gợi ý", true) +
      card("AOV uplift", up == null ? "—" : (up >= 0 ? "+" : "") + up.toFixed(1) + "%",
        vnd(m.aov.withRec.aov) + " vs " + vnd(m.aov.withoutRec.aov), true);

    rows("slots", ["Slot", "Hiển thị", "Chấp nhận", "Tỉ lệ"], m.bySlot.map(s =>
      "<tr><td>" + s.slot + "</td><td class=num>" + s.shown + "</td><td class=num>" + s.accepted +
      "</td><td class=num>" + pct(s.rate) + '<div class="bar"><i style="width:' + Math.min(100, (s.rate || 0) * 100) + '%"></i></div></td></tr>'));

    const tot = m.byStrategy.reduce((a, x) => a + x.accepted, 0) || 1;
    rows("strats", ["Chiến lược", "Chấp nhận", "Tỉ trọng"], m.byStrategy.map(s =>
      "<tr><td>" + s.strategy + "</td><td class=num>" + s.accepted + "</td><td class=num>" + pct(s.accepted / tot) +
      '<div class="bar"><i style="width:' + (s.accepted / tot) * 100 + '%"></i></div></td></tr>'));

    rows("combo", ["", "Giá trị"], [
      "<tr><td>Hiển thị trade-up</td><td class=num>" + m.comboUpsell.shown + "</td></tr>",
      "<tr><td>Nâng cấp thành công</td><td class=num>" + m.comboUpsell.accepted + "</td></tr>",
      "<tr><td>Tỉ lệ</td><td class=num>" + pct(m.comboUpsell.rate) + "</td></tr>",
    ]);

    rows("aov", ["", "Đơn hàng", "AOV"], [
      "<tr><td>Có gợi ý được chấp nhận</td><td class=num>" + m.aov.withRec.orders + "</td><td class=num>" + vnd(m.aov.withRec.aov) + "</td></tr>",
      "<tr><td>Không có</td><td class=num>" + m.aov.withoutRec.orders + "</td><td class=num>" + vnd(m.aov.withoutRec.aov) + "</td></tr>",
    ]);

    document.getElementById("upd").textContent =
      "cập nhật " + new Date().toLocaleTimeString("vi-VN") + " · cửa sổ: " + (days ? days + " ngày" : "tất cả");
  } catch (e) {
    const el = document.getElementById("err");
    el.textContent = "Không tải được metrics: " + e.message;
    el.style.display = "block";
  }
}

document.querySelectorAll(".win button").forEach((b) =>
  b.addEventListener("click", () => {
    days = Number(b.dataset.d);
    document.querySelectorAll(".win button").forEach((x) => x.classList.toggle("on", x === b));
    load();
  }));

load();
setInterval(load, 10000);
</script>
</body>
</html>`;
