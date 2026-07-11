"""
Zero-build web chat harness for the P4 agent, served at GET /agent/ui.

This is the DEV HARNESS + DEMO FALLBACK, not the product: the same chat()
loop will sit behind the Zalo OA webhook. Simulates the Zalo channel
(context.channel = "zalo") so carts/orders/metrics are attributed correctly.
"""

CHAT_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KFC Chat Agent (demo)</title>
<style>
  :root { --red: #e4002b; --bg: #f0f2f5; }
  * { box-sizing: border-box; margin: 0; }
  body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; background: var(--bg); height: 100vh; display: flex; justify-content: center; }
  .phone { width: 100%; max-width: 420px; height: 100vh; display: flex; flex-direction: column; background: #fff; box-shadow: 0 0 20px rgba(0,0,0,.12); }
  header { background: var(--red); color: #fff; padding: 12px 16px; display: flex; align-items: center; gap: 10px; }
  header .avatar { width: 34px; height: 34px; border-radius: 50%; background: #fff; color: var(--red); font-weight: 900; display: flex; align-items: center; justify-content: center; }
  header .t { flex: 1; } header .t b { display: block; font-size: 15px; }
  header .t span { font-size: 11px; opacity: .85; }
  header button { background: rgba(255,255,255,.2); border: 0; color: #fff; border-radius: 8px; padding: 6px 10px; cursor: pointer; font-size: 12px; }
  #log { flex: 1; overflow-y: auto; padding: 14px; display: flex; flex-direction: column; gap: 8px; background: var(--bg); }
  .msg { max-width: 82%; padding: 9px 12px; border-radius: 16px; font-size: 14px; line-height: 1.45; white-space: pre-wrap; word-break: break-word; }
  .user { align-self: flex-end; background: var(--red); color: #fff; border-bottom-right-radius: 4px; }
  .bot { align-self: flex-start; background: #fff; border: 1px solid #e5e5e5; border-bottom-left-radius: 4px; }
  .tools { align-self: flex-start; display: flex; flex-wrap: wrap; gap: 4px; }
  .tools span { font-size: 10px; background: #e8eefc; color: #3358c4; border-radius: 10px; padding: 2px 8px; font-family: ui-monospace, monospace; }
  .typing { align-self: flex-start; color: #999; font-size: 12px; padding: 4px 8px; }
  form { display: flex; gap: 8px; padding: 10px; border-top: 1px solid #eee; background: #fff; }
  input { flex: 1; border: 1px solid #ddd; border-radius: 20px; padding: 10px 14px; font-size: 14px; outline: none; }
  input:focus { border-color: var(--red); }
  form button { background: var(--red); color: #fff; border: 0; border-radius: 20px; padding: 0 18px; font-weight: 700; cursor: pointer; }
  .hints { display: flex; gap: 6px; padding: 8px 10px 0; flex-wrap: wrap; background: #fff; }
  .hints button { font-size: 11px; border: 1px solid #eee; background: #fafafa; border-radius: 12px; padding: 4px 10px; cursor: pointer; color: #555; }
</style>
</head>
<body>
<div class="phone">
  <header>
    <div class="avatar">K</div>
    <div class="t"><b>KFC Việt Nam</b><span id="sess"></span></div>
    <button onclick="resetSession()">Phiên mới</button>
  </header>
  <div id="log"></div>
  <div class="hints">
    <button onclick="say('Cho mình 2 miếng gà giòn cay và 1 pepsi')">2 gà cay + pepsi</button>
    <button onclick="say('Có combo nào cho 1 người không?')">Combo 1 người?</button>
    <button onclick="say('Mình là thành viên, sđt 0900000001')">Đăng nhập TV</button>
    <button onclick="say('Chốt đơn nhé')">Chốt đơn</button>
  </div>
  <form onsubmit="return send(event)">
    <input id="inp" placeholder="Nhắn tin cho KFC…" autocomplete="off">
    <button>Gửi</button>
  </form>
</div>
<script>
let sessionId = "web-" + Math.random().toString(36).slice(2, 10);
document.getElementById("sess").textContent = "phiên " + sessionId;
const log = document.getElementById("log");

function bubble(cls, text) {
  const d = document.createElement("div");
  d.className = "msg " + cls;
  d.textContent = text;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
  return d;
}
function toolChips(trace) {
  if (!trace || !trace.length) return;
  const d = document.createElement("div");
  d.className = "tools";
  d.innerHTML = trace.map(t => "<span>" + t.tool + "</span>").join("");
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}
function say(text) { document.getElementById("inp").value = text; send(); }

async function send(e) {
  if (e) e.preventDefault();
  const inp = document.getElementById("inp");
  const text = inp.value.trim();
  if (!text) return false;
  inp.value = "";
  bubble("user", text);
  const typing = document.createElement("div");
  typing.className = "typing"; typing.textContent = "đang nhập…";
  log.appendChild(typing); log.scrollTop = log.scrollHeight;
  try {
    const r = await fetch("/agent/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sessionId, message: text, context: { channel: "zalo", externalId: sessionId } }),
    });
    const data = await r.json();
    typing.remove();
    toolChips(data.toolTrace);
    bubble("bot", data.reply || "(không có phản hồi)");
  } catch (err) {
    typing.remove();
    bubble("bot", "Lỗi kết nối agent: " + err.message);
  }
  return false;
}

function resetSession() {
  sessionId = "web-" + Math.random().toString(36).slice(2, 10);
  document.getElementById("sess").textContent = "phiên " + sessionId;
  log.innerHTML = "";
  bubble("bot", "Xin chào! Mình là trợ lý đặt món KFC. Bạn muốn ăn gì hôm nay? 🍗");
}
resetSession();
</script>
</body>
</html>"""
