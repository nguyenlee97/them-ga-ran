# Test & Demo Scenarios — kiosk + chat

Run top to bottom. Each scenario: **do → expect**. Login = phone + ANY code
(mock OTP). Demo phones: `0900000001` An (gà+Pepsi), `0900000002` Bích
(tráng miệng), `0900000003` Cường (gia đình cuối tuần).

Note: `timeOfDay` comes from the kiosk clock — dessert suggestions are
strongest in the afternoon (14–17h); late evening = "late" context.

---

## A. Contextual recommendations (NO login — the anonymous workhorse)

**A1. Rule-based attach (the classic).**
Dine-in → Bỏ qua (skip login) → add **1 Miếng Gà Giòn Cay**.
→ Item-added modal: **Pepsi (~71% khách mua cùng)** + khoai tây + bánh trứng.
Reasons show real co-purchase %. No combos in the strip.

**A2. Cart-awareness (recs react to what you add).**
Accept the Pepsi (tap **+ Thêm**) → open cart.
→ **No drink suggested anymore** (category covered) — suggestions move to
side/dessert. This is the "recs follow the cart" money-shot.

**A3. Combo covers drink+side.**
New order → add any **Combo 1 Người**.
→ Recs suggest only dessert/snack — never a drink/side (combo bundles them),
never another combo as an add-on.

**A4. Combo trade-up (à-la-carte → combo).**
New order → add 1 chicken piece alone.
→ Amber **"Nâng cấp lên Combo"** card: matching combo (name-matched, e.g.
tiêu chanh → Combo Tiêu...), price delta shown. Tap **Nâng cấp** → covered
items swapped for the combo in cart.

**A5. Trade-up with savings.**
Add chicken + khoai tây + Pepsi as separate items.
→ Trade-up card shows **"tiết kiệm ..."** when the combo is cheaper than the
sum (delta negative, green).

---

## B. Personalization (login required — the headline)

**B1. Same cart, different members.**
Log in as **0900000002 (Bích)** → add 1 chicken piece.
→ Dessert ranked high with **"Món bạn hay gọi"** / **"Hợp gu bạn"** prefix.
Log out, new session as **0900000001 (An)** → same chicken.
→ His favorite **Pepsi variant** leads with "Món bạn hay gọi".
Same input, different output = personalization visible.

**B2. Family persona.**
Log in as **0900000003 (Cường)** → add 2–3 chicken pieces.
→ Trade-up leans big/group combos; drink/dessert recs reflect family basket
habits.

**B3. Cold start (graceful).**
Log in with a NEW phone (e.g. `0912000333`) → add chicken.
→ Recs identical to anonymous — sensible, nothing broken. (API `explain`
shows `personalize_cold_start`, n_history 0–2.)

**B4. LIVE LEARNING — the demo climax.**
Still on the new phone: order **a dessert, pay (mock)**. Repeat once more
(2–3 dessert orders total).
→ Start a new order, add a chicken piece:
**dessert now ranks top with "Món bạn hay gọi"** — the system learned from
orders placed MINUTES ago (order→transactions feedback loop, recency-weighted).
No pre-baked data needed: it learns on stage.

**B5. Login mid-order.**
Anonymous → add items → from cart, log in as a member → recs refresh
personalized; order earns points for the member.

---

## C. Metrics evidence (run alongside A & B)

**C1.** Keep `http://localhost:3000/api/admin/dashboard` open in a second tab.
While doing A1–B5: impressions count up; every **+ Thêm** = acceptance;
combo **Nâng cấp** = combo accepted; each paid order lands in the AOV table.
→ After a few orders (some with accepted recs, some plain): **AOV with-rec >
without-rec, uplift % positive** — the brief's 10–15% AOV story with live data.

**C2.** Strategy table shows which layer sells: assoc_rule vs context_pop vs
personalized.

---

## D. Chat agent — `http://localhost:8080/agent/ui` (needs working OPENAI key)

**D1. Natural ordering.** "Cho mình 2 miếng gà giòn cay và 1 pepsi"
→ tool chips: search_menu → create_cart → add_to_cart; reply lists real
items + prices (backend-sourced, never invented).

**D2. Proactive upsell.** After adding items, agent suggests 1 add-on
(get_recommendations) without being pushy.

**D3. Member link.** "Mình là thành viên, sđt 0900000001"
→ link_channel; greets An with loyalty stats; cart now tied to the member
(order will earn points + feed his personalization).

**D4. Confirm-before-commit.** "Chốt đơn nhé"
→ Agent READS BACK items + total first, waits for explicit "OK" → then
place_order → order id + points. Never commits without confirmation.

**D5. Session memory + fresh cart.** Say "đặt thêm 1 pepsi" after the order
→ a NEW cart is created (old one committed); agent still remembers who you are.

**D6. Handoff.** "Tôi muốn khiếu nại, cho tôi gặp nhân viên"
→ handoff tool fires; polite escalation message.

**D7. Voucher.** Check available codes at `http://localhost:3000/api/vouchers`,
then in chat: "Áp mã <CODE> cho mình" → discount reflected in the total
readback (or a clear rejection reason).

**D8. Cross-channel proof.** After D4, refresh the dashboard: the chat order
appears in orders/AOV (channel `zalo`) — ONE brain, two front doors.

---

## Quick reset between demo runs

Orders/events accumulate. For a clean stage run: `npm run seed` re-seeds
users/transactions/rules (events & orders currently persist — a demo-reset
endpoint is on the roadmap).
