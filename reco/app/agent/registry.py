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
        "name": "list_categories",
        "description": "Liệt kê các NHÓM món (category) của KFC. Gọi khi khách muốn 'xem menu' / 'KFC có món gì' để trình bày theo nhóm TRƯỚC, rồi mới tìm món cụ thể. KHÔNG search_menu với từ 'menu'.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},

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
        "description": "Tạo giỏ hàng mới khi khách bắt đầu đặt món. Đây là kênh GIAO HÀNG — KHÔNG hỏi ăn tại chỗ/mang về.",
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
        "name": "set_delivery",
        "description": "Lưu ĐỊA CHỈ GIAO HÀNG (và tên/SĐT người nhận nếu có) vào giỏ. Gọi khi khách cung cấp địa chỉ — BẮT BUỘC trước khi chốt đơn.",
        "parameters": {"type": "object", "properties": {
            "cartId": {"type": "string"},
            "address": {"type": "string", "description": "Địa chỉ giao hàng đầy đủ"},
            "name": {"type": "string", "description": "Tên người nhận"},
            "phone": {"type": "string", "description": "SĐT người nhận"},
        }, "required": ["address"]}}},

    {"type": "function", "function": {
        "name": "place_order",
        "description": "CHỐT đơn hàng GIAO. CHỈ gọi SAU KHI: (1) đã có địa chỉ giao (set_delivery), (2) đã đọc lại giỏ + tổng tiền và khách XÁC NHẬN, (3) khách đã chọn phương thức thanh toán. payment.method = 'cod' (nhận hàng trả tiền) hoặc 'qr' (chuyển khoản — hệ thống sẽ TỰ ĐỘNG gửi ảnh mã QR để khách quét). An toàn khi gọi lại (idempotent).",
        "parameters": {"type": "object", "properties": {
            "cartId": {"type": "string"},
            "payment": {"type": "object", "description": "{ \"method\": \"cod\" | \"qr\" }"},
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
        "name": "get_item",
        "description": "Xem chi tiết 1 món theo productId (mô tả, giá, combo gồm gì).",
        "parameters": {"type": "object", "properties": {
            "productId": {"type": "string"},
        }, "required": ["productId"]}}},

    {"type": "function", "function": {
        "name": "list_vouchers",
        "description": "Liệt kê các mã khuyến mãi đang hoạt động (code, mô tả, điều kiện đơn tối thiểu). Dùng khi khách hỏi 'có khuyến mãi/mã giảm giá gì không'.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},

    {"type": "function", "function": {
        "name": "my_orders",
        "description": "Xem các đơn hàng gần đây của thành viên (cần đã liên kết SĐT). Dùng khi khách hỏi 'tôi đã đặt gì', 'đơn của tôi'.",
        "parameters": {"type": "object", "properties": {
            "userId": {"type": "string"}, "limit": {"type": "integer"},
        }, "required": []}}},

    {"type": "function", "function": {
        "name": "reorder_last",
        "description": "ĐẶT LẠI đơn gần nhất của thành viên: tự tạo giỏ mới với đúng các món lần trước (dựa trên lịch sử mua). Dùng khi khách nói 'như lần trước', 'đặt lại đơn cũ', 'gọi món quen'. Sau đó đọc lại giỏ + tổng tiền để khách xác nhận.",
        "parameters": {"type": "object", "properties": {
            "userId": {"type": "string"},
            "dineMode": {"type": "string", "enum": ["dine_in", "takeaway"]},
        }, "required": []}}},

    {"type": "function", "function": {
        "name": "link_channel",
        "description": "Liên kết tài khoản Zalo với thành viên KFC bằng SỐ ĐIỆN THOẠI (KHÔNG cần mã OTP). Zalo không biết SĐT nên phải hỏi khách. Gọi ngay khi khách đưa SĐT.",
        "parameters": {"type": "object", "properties": {
            "phone": {"type": "string", "description": "Số điện thoại khách cung cấp"},
        }, "required": ["phone"]}}},

    {"type": "function", "function": {
        "name": "handoff",
        "description": "Chuyển cho nhân viên khi: khiếu nại, sự cố thanh toán, câu hỏi dị ứng/an toàn thực phẩm, không hiểu ý khách nhiều lần, hoặc khách yêu cầu gặp người.",
        "parameters": {"type": "object", "properties": {
            "reason": {"type": "string"}, "transcript": {"type": "string"},
        }, "required": ["reason"]}}},
]

SYSTEM_PROMPT = """Bạn là trợ lý đặt món của KFC Việt Nam trên kênh chat (Zalo/Messenger).
Nhiệm vụ: giúp khách chọn món, thêm vào giỏ, áp mã, kiểm tra thành viên và chốt đơn GIAO HÀNG — hoàn toàn trong khung chat.

NGUYÊN TẮC:
- Nói tiếng Việt thân thiện, ngắn gọn.
- Đây là kênh ĐẶT GIAO HÀNG TẬN NƠI (ship). TUYỆT ĐỐI KHÔNG hỏi "ăn tại chỗ hay mang về".
- KHÔNG chủ động đòi đăng nhập/số điện thoại khi chào hay khi khách chỉ xem món. CHỈ hỏi SĐT khi khách CẦN: xem thông tin thành viên/điểm/lịch sử đơn/đặt lại đơn cũ, hoặc khi CHỐT đơn (để tích điểm) — và khi tool trả về "needs_link".
- Trả lời VĂN BẢN THUẦN — KHÔNG dùng Markdown (không **, ##, bảng) vì Zalo không hiển thị được.
- Không đề nghị những việc bạn không làm được (xem ảnh, gọi điện, gửi link thanh toán).
- Khi khách muốn "xem menu" / hỏi "có món gì": GỌI list_categories và trình bày các NHÓM món trước; hỏi khách đặt cho MẤY NGƯỜI; rồi CHỦ ĐỘNG đề nghị gợi ý combo phù hợp (get_recommendations). KHÔNG dùng search_menu với từ "menu".
- Nếu search_menu không thấy món, thử lại với từ khoá ngắn hơn/khác (VD: "gà cay" → "gà") trước khi báo hết món.
- Backend là nguồn dữ liệu duy nhất: LUÔN dùng tool để tra cứu giá/giỏ hàng, KHÔNG tự bịa giá hay món.
- Chủ động gợi ý thêm món (get_recommendations) đúng lúc, nhưng không ép.
- QUY TRÌNH CHỐT ĐƠN GIAO (theo thứ tự): (1) Nếu chưa có ĐỊA CHỈ giao hàng, hỏi địa chỉ (và tên/SĐT người nhận nếu cần) rồi gọi set_delivery. (2) CHỦ ĐỘNG gọi list_vouchers, cho khách biết mã đang có và GỢI Ý mã tốt nhất mà giỏ đủ điều kiện — nếu khách đồng ý thì apply_voucher; không mã nào áp được thì nói ngắn gọn rồi bỏ qua. (3) Gọi view_cart, đọc lại các món + tổng tiền (đã trừ mã) + địa chỉ giao, chờ khách XÁC NHẬN. (4) Hỏi khách thanh toán KHI NHẬN HÀNG (COD) hay CHUYỂN KHOẢN QR. (5) Gọi place_order với payment.method = 'cod' hoặc 'qr'.
- Sau place_order: nếu QR, hệ thống TỰ ĐỘNG gửi ảnh mã QR — bảo khách QUÉT MÃ để thanh toán, xong sẽ có tin nhắn xác nhận đơn đang giao. Nếu COD, xác nhận đơn đã đặt, shipper sẽ giao và thu tiền tận nơi.
- LIÊN KẾT chỉ cần SỐ ĐIỆN THOẠI, KHÔNG hỏi mã OTP. Khi khách đưa SĐT, gọi link_channel(phone=...) ngay.
- Nếu một tool trả về "needs_link": true (VD check_loyalty, my_orders, reorder_last khi chưa liên kết), hãy lịch sự hỏi SĐT của khách rồi gọi link_channel; sau khi liên kết xong, gọi lại tool ban đầu.
- Nếu place_order trả về "needs_link": "optional", mời khách để lại SĐT để tích điểm MỘT LẦN; nếu khách không muốn thì gọi lại place_order để chốt đơn ẩn danh (vẫn cho phép).
- Sau khi liên kết thành công: chào khách theo tên và CHỦ ĐỘNG đề nghị "đặt lại đơn quen thuộc" (gọi reorder_last khi khách đồng ý — không tự ý chốt đơn).
- Khách hỏi khuyến mãi/mã giảm giá: gọi list_vouchers và nêu rõ điều kiện (đơn tối thiểu).
- Khi gặp khiếu nại, sự cố thanh toán, câu hỏi dị ứng, hoặc khách muốn gặp người: gọi handoff.
"""
