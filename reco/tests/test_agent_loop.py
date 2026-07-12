import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch


sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.agent import loop


class AgentLoopMemoryTests(unittest.TestCase):
    def test_system_prompt_contains_natural_chat_style_guardrails(self):
        self.assertIn("GIỌNG ĐIỆU", loop.SYSTEM_PROMPT)
        self.assertIn("Không lặp \"ạ\"", loop.SYSTEM_PROMPT)
        self.assertIn("MỘT câu hỏi/bước tiếp theo", loop.SYSTEM_PROMPT)
        self.assertIn("HANDOFF BẮT BUỘC", loop.SYSTEM_PROMPT)
        self.assertIn("đã bị trừ tiền", loop.SYSTEM_PROMPT)

    def test_active_sessions_receive_the_latest_deployed_prompt(self):
        bounded = loop._bounded_messages([
            {"role": "system", "content": "old prompt"},
            {"role": "user", "content": "hi"},
        ])
        self.assertEqual(bounded[0]["content"], loop.SYSTEM_PROMPT)

    def test_customer_reply_removes_internal_component_language(self):
        reply = loop._sanitize(
            "Combo giá 169.000đ ạ.\nBackend chưa trả chi tiết món.\nBạn muốn chọn món này không?"
        )
        self.assertNotIn("Backend", reply)
        self.assertIn("chưa có đủ thông tin", reply)
        self.assertIn("Combo giá 169.000đ", reply)

    def test_personal_lookup_of_another_phone_is_blocked_but_delivery_is_not(self):
        ctx = {
            "userId": "member-1",
            "identityUser": {"phone": "0918008888", "name": "Nguyên"},
        }
        blocked = loop._other_member_phone_reply(
            "mình muốn kiểm tra lịch sử đơn hàng của sđt 0918434356", ctx
        )
        self.assertIn("0918***888", blocked)
        self.assertIn("0918***356", blocked)
        self.assertIn("không thể tra cứu", blocked)
        self.assertIsNone(loop._other_member_phone_reply(
            "giao đơn này cho số 0918434356", ctx
        ))

    def test_member_onboarding_uses_complete_fixed_customer_copy(self):
        session = {
            "sessionId": "zalo-1",
            "messages": [{"role": "system", "content": "system"}],
            "state": {},
            "lastActivityAt": datetime.now(timezone.utc),
        }
        assistant_tool_call = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "call-1",
                "type": "function",
                "function": {"name": "my_orders", "arguments": "{}"},
            }],
        }
        with patch.object(loop, "load_session", return_value=session), \
                patch.object(loop, "resolve_identity", return_value={"linked": False}), \
                patch.object(loop, "save_session"), \
                patch.object(loop.llm_client, "available", return_value=True), \
                patch.object(loop.llm_client, "chat", return_value=assistant_tool_call) as llm:
            result = loop.chat(
                "zalo-1", "mình muốn kiểm tra đơn hàng cũ",
                {"channel": "zalo", "externalId": "zalo-1"},
            )
        self.assertEqual(llm.call_count, 1)
        self.assertIn("Mỗi tài khoản Zalo chỉ xem", result["reply"])
        self.assertIn("SĐT nhận hàng khác", result["reply"])

    def test_cross_phone_lookup_bypasses_llm_after_idle_reset(self):
        session = {
            "sessionId": "zalo-1",
            "messages": [{"role": "user", "content": "old"}],
            "state": {"userId": "member-1"},
            "lastActivityAt": datetime.now(timezone.utc) - timedelta(minutes=18),
        }
        with patch.object(loop, "load_session", return_value=session), \
                patch.object(loop, "resolve_identity", return_value={
                    "linked": True,
                    "user": {"id": "member-1", "phone": "0918008888", "name": "Nguyên"},
                }), \
                patch.object(loop, "save_session"), \
                patch.object(loop.llm_client, "chat") as llm:
            result = loop.chat(
                "zalo-1", "kiểm tra lịch sử đơn hàng của sđt 0918434356",
                {"channel": "zalo", "externalId": "zalo-1"},
            )
        llm.assert_not_called()
        self.assertIn("không thể tra cứu", result["reply"])

    def test_legacy_session_without_activity_timestamp_expires(self):
        session = {"messages": [{"role": "user", "content": "cũ"}]}
        self.assertTrue(loop._conversation_expired(session))

    def test_recent_session_stays_active_and_idle_session_expires(self):
        now = datetime.now(timezone.utc)
        with patch.object(loop.config, "CHAT_IDLE_TIMEOUT_SECONDS", 600):
            self.assertFalse(loop._conversation_expired(
                {"messages": [{}], "lastActivityAt": now - timedelta(seconds=599)}, now
            ))
            self.assertTrue(loop._conversation_expired(
                {"messages": [{}], "lastActivityAt": now - timedelta(seconds=601)}, now
            ))

    def test_context_cap_starts_at_a_user_boundary(self):
        messages = [{"role": "system", "content": "system"}]
        for i in range(12):
            messages.extend([
                {"role": "user", "content": f"u{i}"},
                {"role": "assistant", "content": f"a{i}"},
            ])
        with patch.object(loop.config, "CHAT_CONTEXT_MESSAGES", 20):
            bounded = loop._bounded_messages(messages)
        self.assertEqual(bounded[0]["role"], "system")
        self.assertEqual(bounded[1]["role"], "user")
        self.assertLessEqual(len(bounded) - 1, 20)

    def test_context_cap_keeps_tool_call_and_result_together(self):
        messages = [{"role": "system", "content": "system"}]
        for i in range(8):
            messages.extend([
                {"role": "user", "content": f"u{i}"},
                {"role": "assistant", "content": None, "tool_calls": [{"id": f"c{i}"}]},
                {"role": "tool", "tool_call_id": f"c{i}", "content": "{}"},
                {"role": "assistant", "content": f"a{i}"},
            ])
        with patch.object(loop.config, "CHAT_CONTEXT_MESSAGES", 20):
            bounded = loop._bounded_messages(messages)
        body = bounded[1:]
        self.assertEqual(body[0]["role"], "user")
        seen_calls = {
            call["id"]
            for message in body
            for call in (message.get("tool_calls") or [])
        }
        for message in body:
            if message.get("role") == "tool":
                self.assertIn(message["tool_call_id"], seen_calls)

    def test_pending_checkout_phone_links_and_places_order(self):
        calls = []

        def fake_link(**kwargs):
            calls.append(("link_channel", kwargs))
            return {"linked": True, "user": {"id": "member-1", "name": "Nguyên"}}

        def fake_place(**kwargs):
            calls.append(("place_order", kwargs))
            return {"orderId": "order-1", "qrImageUrl": "https://example/qr"}

        ctx = {
            "sessionId": "zalo-1", "externalId": "zalo-1", "channel": "zalo",
            "cartId": "cart-1", "orderLinkPitched": False,
        }
        with patch.dict(loop.DISPATCH, {"link_channel": fake_link, "place_order": fake_place}), \
                patch.object(loop, "attach_user_to_cart", return_value={}):
            gated = loop._run_tool("place_order", {"payment": {"method": "qr"}}, ctx)
            self.assertEqual(gated["needs_link"], "optional")
            notes, trace = loop._resume_pending_link("SĐT 0918 008 888", ctx)

        self.assertEqual([name for name, _ in calls], ["link_channel", "place_order"])
        self.assertEqual(ctx["userId"], "member-1")
        self.assertEqual(ctx["pendingImageUrl"], "https://example/qr")
        self.assertIsNone(ctx["pendingAfterLink"])
        self.assertEqual(len(trace), 2)
        self.assertTrue(notes)

    def test_trusted_context_overrides_model_identity_fields(self):
        captured = {}

        def fake_create(**kwargs):
            captured.update(kwargs)
            return {"cartId": "cart-1"}

        ctx = {
            "sessionId": "zalo-1", "externalId": "zalo-1", "channel": "zalo",
            "userId": "member-1",
        }
        with patch.dict(loop.DISPATCH, {"create_cart": fake_create}):
            loop._run_tool(
                "create_cart",
                {"channel": "chat", "userId": "wrong-member", "dineMode": "delivery"},
                ctx,
            )
        self.assertEqual(captured["channel"], "zalo")
        self.assertEqual(captured["userId"], "member-1")

    def test_link_channel_cannot_switch_an_existing_member(self):
        called = []

        def fake_link(**kwargs):
            called.append(kwargs)
            return {"linked": True}

        ctx = {
            "sessionId": "zalo-1", "externalId": "zalo-1", "channel": "zalo",
            "userId": "member-1",
        }
        with patch.dict(loop.DISPATCH, {"link_channel": fake_link}):
            result = loop._run_tool("link_channel", {"phone": "0900000001"}, ctx)
        self.assertTrue(result["already_linked"])
        self.assertEqual(called, [])

    def test_member_tools_cannot_read_a_model_supplied_other_user(self):
        captured = {}

        def fake_loyalty(**kwargs):
            captured.update(kwargs)
            return {"userId": kwargs["userId"]}

        ctx = {
            "sessionId": "zalo-1", "externalId": "zalo-1", "channel": "zalo",
            "userId": "member-1",
        }
        with patch.dict(loop.DISPATCH, {"check_loyalty": fake_loyalty}):
            result = loop._run_tool("check_loyalty", {"userId": "victim-member"}, ctx)
        self.assertEqual(captured["userId"], "member-1")
        self.assertEqual(result["userId"], "member-1")

    def test_successful_handoff_has_fixed_wait_notice(self):
        def fake_handoff(**kwargs):
            return {"ok": True, "status": "queued"}

        ctx = {
            "sessionId": "zalo-1", "externalId": "zalo-1", "channel": "zalo",
        }
        with patch.dict(loop.DISPATCH, {"handoff": fake_handoff}):
            result = loop._run_tool("handoff", {"reason": "payment_dispute"}, ctx)
        self.assertEqual(result["status"], "queued")
        self.assertIn("nhân viên hỗ trợ trực tiếp", result["customer_message"])
        self.assertIn("vui lòng chờ", result["customer_message"])

    def test_backend_identity_is_authoritative_and_injected_each_turn(self):
        captured = {}
        session = {
            "sessionId": "zalo-1",
            "messages": [{"role": "system", "content": "system"}],
            "state": {"userId": "stale-member"},
            "lastActivityAt": datetime.now(timezone.utc),
        }

        def fake_chat(messages, **kwargs):
            captured["messages"] = messages
            return {"role": "assistant", "content": "Mình kiểm tra ngay ạ."}

        with patch.object(loop, "load_session", return_value=session), \
                patch.object(loop, "resolve_identity", return_value={
                    "linked": True,
                    "user": {"id": "member-1", "name": "Nguyên", "tier": "gold"},
                }), \
                patch.object(loop, "save_session"), \
                patch.object(loop.llm_client, "available", return_value=True), \
                patch.object(loop.llm_client, "chat", side_effect=fake_chat):
            result = loop.chat(
                "zalo-1", "kiểm tra tài khoản",
                {"channel": "zalo", "externalId": "zalo-1"},
            )

        self.assertEqual(result["userId"], "member-1")
        runtime = captured["messages"][1]["content"]
        self.assertIn("ĐÃ liên kết", runtime)
        self.assertIn("KHÔNG hỏi lại SĐT", runtime)

    def test_unlinked_backend_identity_clears_stale_session_user(self):
        captured = {}
        session = {
            "sessionId": "zalo-1",
            "messages": [{"role": "system", "content": "system"}],
            "state": {"userId": "stale-member"},
            "lastActivityAt": datetime.now(timezone.utc),
        }

        def fake_chat(messages, **kwargs):
            captured["messages"] = messages
            return {"role": "assistant", "content": "Bạn muốn kiểm tra gì ạ?"}

        with patch.object(loop, "load_session", return_value=session), \
                patch.object(loop, "resolve_identity", return_value={"linked": False}), \
                patch.object(loop, "save_session"), \
                patch.object(loop.llm_client, "available", return_value=True), \
                patch.object(loop.llm_client, "chat", side_effect=fake_chat):
            result = loop.chat(
                "zalo-1", "xin chào",
                {"channel": "zalo", "externalId": "zalo-1"},
            )

        self.assertIsNone(result["userId"])
        self.assertIn("chưa liên kết", captured["messages"][1]["content"])


if __name__ == "__main__":
    unittest.main()
