"""
OpenAI tool (function) schemas for the KFC conversational ordering agent.
Descriptions are in Vietnamese (primary channel language). Each maps 1:1 to a
wrapper in tools.py → a backend endpoint.
"""

TOOL_DEFINITIONS = [
    {"type": "function", "function": {
        "name": "search_menu",
        "description": "Tìm món trong thực đơn KFC theo từ khoá/danh mục/giá. Dùng khi khách hỏi có món gì, giá bao nhiêu.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Từ khoá (VD: 'gà rán', 'combo', 'pepsi')"},
            "category": {"type": "string"},
            "maxPrice": {"type": "number"},
        }, "required": []}}},

    {"type": "function", "function": {
        "name": "get_recommendations",
        "description": "Gợi ý món thêm (upsell/cross-sell) dựa trên giỏ hàng và ngữ cảnh. Gọi sau khi khách thêm món hoặc trước khi thanh toán.",
        "parameters": {"type": "object", "properties": {
            "context": {"type": "object", "description": "{cartId, timeOfDay, dineMode, channel, userId}"},
            "slot": {"type": "string", "enum": ["cart", "item_added", "checkout"]},
            "limit": {"type": "integer"},
        }, "required": ["context"]}}},

    {"type": "function", "function": {
        "name": "create_cart",
        "description": "Tạo giỏ hàng mới khi khách bắt đầu đặt món. Nhớ hỏi ăn tại chỗ hay mang về.",
        "parameters": {"type": "object", "properties": {
            "channel": {"type": "string"}, "storeId": {"type": "string"},
            "dineMode": {"type": "string", "enum": ["dine_in", "takeaway"]},
            "userId": {"type": "string"},
        }, "required": []}}},

    {"type": "function", "function": {
        "name": "add_to_cart",
        "description": "Thêm món vào giỏ hàng. Cần cartId và productId.",
        "parameters": {"type": "object", "properties": {
            "cartId": {"type": "string"}, "productId": {"type": "string"},
            "qty": {"type": "integer"}, "modifiers": {"type": "array"},
        }, "required": ["cartId", "productId"]}}},

    {"type": "function", "function": {
        "name": "remove_from_cart",
        "description": "Xoá 1 dòng món khỏi giỏ hàng theo lineId.",
        "parameters": {"type": "object", "properties": {
            "cartId": {"type": "string"}, "lineId": {"type": "string"},
        }, "required": ["cartId", "lineId"]}}},

    {"type": "function", "function": {
        "name": "view_cart",
        "description": "Xem giỏ hàng hiện tại và tổng tiền. Dùng để đọc lại đơn cho khách xác nhận.",
        "parameters": {"type": "object", "properties": {"cartId": {"type": "string"}}, "required": ["cartId"]}}},

    {"type": "function", "function": {
        "name": "apply_voucher",
        "description": "Áp dụng mã khuyến mãi vào giỏ hàng.",
        "parameters": {"type": "object", "properties": {
            "cartId": {"type": "string"}, "code": {"type": "string"},
        }, "required": ["cartId", "code"]}}},

    {"type": "function", "function": {
        "name": "check_loyalty",
        "description": "Kiểm tra thông tin thành viên: số lần ăn KFC, tổng đơn, hạng, điểm tích luỹ. Cần userId (khách đã đăng nhập).",
        "parameters": {"type": "object", "properties": {"userId": {"type": "string"}}, "required": ["userId"]}}},

    {"type": "function", "function": {
        "name": "place_order",
        "description": "CHỐT đơn hàng. CHỈ gọi SAU KHI đã đọc lại giỏ hàng + tổng tiền và khách XÁC NHẬN rõ ràng. An toàn khi gọi lại (idempotent).",
        "parameters": {"type": "object", "properties": {
            "cartId": {"type": "string"}, "idempotencyKey": {"type": "string"},
            "payment": {"type": "object"},
        }, "required": ["cartId"]}}},

    {"type": "function", "function": {
        "name": "get_order_status",
        "description": "Tra cứu trạng thái đơn hàng theo orderId.",
        "parameters": {"type": "object", "properties": {"orderId": {"type": "string"}}, "required": ["orderId"]}}},

    {"type": "function", "function": {
        "name": "list_stores",
        "description": "Liệt kê cửa hàng KFC (có thể lọc theo thành phố).",
        "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": []}}},

    {"type": "function", "function": {
        "name": "link_channel",
        "description": "Liên kết tài khoản chat (Zalo OA) với thành viên KFC qua số điện thoại + mã OTP. Zalo OA không biết SĐT nên phải hỏi khách.",
        "parameters": {"type": "object", "properties": {
            "channel": {"type": "string"}, "externalId": {"type": "string"},
            "phone": {"type": "string"}, "code": {"type": "string"},
        }, "required": ["channel", "externalId", "phone", "code"]}}},

    {"type": "function", "function": {
        "name": "handoff",
        "description": "Chuyển cho nhân viên khi: khiếu nại, sự cố thanh toán, câu hỏi dị ứng/an toàn thực phẩm, không hiểu ý khách nhiều lần, hoặc khách yêu cầu gặp người.",
        "parameters": {"type": "object", "properties": {
            "reason": {"type": "string"}, "transcript": {"type": "string"},
        }, "required": ["reason"]}}},
]

SYSTEM_PROMPT = """Bạn là trợ lý đặt món của KFC Việt Nam trên kênh chat (Zalo/Messenger).
Nhiệm vụ: giúp khách chọn món, thêm vào giỏ, áp mã, kiểm tra thành viên và chốt đơn — hoàn toàn trong khung chat.

NGUYÊN TẮC:
- Nói tiếng Việt thân thiện, ngắn gọn.
- Backend là nguồn dữ liệu duy nhất: LUÔN dùng tool để tra cứu giá/giỏ hàng, KHÔNG tự bịa giá hay món.
- Chủ động gợi ý thêm món (get_recommendations) đúng lúc, nhưng không ép.
- TRƯỚC KHI chốt đơn: gọi view_cart, đọc lại các món + tổng tiền, và chờ khách xác nhận rõ ràng rồi mới gọi place_order.
- Nếu khách chưa đăng nhập mà cần thông tin thành viên/điểm: hướng dẫn liên kết qua link_channel (hỏi số điện thoại).
- Khi gặp khiếu nại, sự cố thanh toán, câu hỏi dị ứng, hoặc khách muốn gặp người: gọi handoff.
"""
