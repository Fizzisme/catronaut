# Ch04 — Công cụ

> Bản dịch cho người đọc của [ch04](../../book-guide/ch04-tools.md). Bản tiếng Anh là bản chuẩn.

**Sách:** [Chương 4 — Công cụ](../../ai-agent-book/ch04-tools.md) · PDF trang 144–169

## Tóm tắt chương

1. **Năm loại tool** (§4.1): tool nhận biết, thực thi và cộng tác, do agent tự gọi; tool giao tiếp với
   người dùng và tool kích hoạt sự kiện, do sự kiện dẫn dắt và được bàn ở ch06.
2. **Hình thức của một năng lực** (§4.2.1) là một dải từ tool chuyên dụng (có cấu trúc, test được, mỗi
   cái tốn hàng trăm token) tới trình thực thi đa năng kèm skill (ít tool, quy trình bằng ngôn ngữ tự
   nhiên). Mặc định chọn đa năng, trừ khi liên quan an toàn và quyền hạn, khác biệt nền tảng, tần suất
   gọi rất cao hoặc tham số phức tạp. Gộp các tool giống nhau. Hình thức (chi phí mỗi năng lực) và mức
   phơi ra (bao nhiêu cái cùng lúc) là hai quyết định độc lập.
3. **Mô tả tool** (§4.2.2) nói khi nào dùng, nói rõ tool không làm được gì, cho ví dụ tham số cụ thể,
   mô tả shape kết quả, nêu chi phí, và kèm 1–5 ví dụ gọi — được báo cáo là nâng độ chính xác gọi tool
   từ ~72% lên ~90%. Khi agent chọn nhầm tool, sửa mô tả trước khi đổ lỗi cho model.
4. **Trung thực tham số** (§4.2.3): không bao giờ âm thầm biến đổi input hay chèn tham số mà model
   không thấy. Mọi chuẩn hóa đều được ghi lại và báo ngược lại.
5. **Hệ sinh thái** (§4.3): MCP chuẩn hóa tool chuyên dụng; Skill Hub phân phối các thư mục
   `SKILL.md`. Cả hai đều là rủi ro chuỗi cung ứng — đầu độc mô tả, bản cập nhật bị chiếm quyền, tool
   giả mạo — giảm thiểu bằng review, ghim phiên bản và credential quyền tối thiểu.
6. **Quá nhiều tool** (§4.4): nhóm phân tầng, nạp theo nhu cầu, lọc trước bằng truy hồi, khám phá chủ
   động và skills. Schema đã nạp được gắn vào đuôi rồi ghim lại.
7. **Tool nhận biết** (§4.5): danh sách ứng viên có cấu trúc kèm phân trang; đọc có `offset`/`limit`;
   khi cắt ngắn phải nói bỏ đi bao nhiêu và cách đọc phần còn lại, nếu không agent sẽ tin là đã thấy
   hết. Tool chỉ-đọc an toàn để cache và chạy song song. Nhận biết đa phương thức (§4.5.1) có ba cách:
   native, trích xuất ra văn bản, hoặc tool phân tích như `analyze_image(file, question) -> text` để
   pixel không lọt vào context chính.
8. **Tool thực thi cần phòng thủ nhiều lớp** (§4.6): validate input kiểu fail-fast, không "tự sửa
   thông minh"; kiểm soát quyền; Proposer–Reviewer phê duyệt trước cho hành động không đảo ngược, tác
   động lớn, và kiểm chứng sau bằng cách đổi phương thức (render rồi xem, chạy trong sandbox); bộ phân
   loại sidecar chỉ nhìn call có cấu trúc; verify-after-write trả về lỗi có cấu trúc; output giữ đầu +
   cuối và lưu bản đầy đủ; thang độ mạnh của sandbox; quan sát từng call; ngữ nghĩa idempotency và
   cancel.
9. **Tool cộng tác** (§4.7): các primitive `spawn`, `send`, `cancel`, `list`; prompt của sub-agent gắn
   nhãn mọi nguồn input, nêu ranh giới và cố định định dạng output; con người trong vòng lặp cần
   timeout, hành động mặc định và vòng phản hồi.

## Các bước áp dụng

1. **Phân loại mọi năng lực** thành nhận biết, thực thi hay cộng tác, và ghi chú cái nào do sự kiện
   dẫn dắt. (§4.1)
2. **Chọn hình thức có chủ đích.** Mặc định là trình thực thi đa năng kèm skills; làm tool chuyên dụng
   cho an toàn và quyền hạn, khác biệt nền tảng, tần suất rất cao hoặc tham số phức tạp; gộp các tool
   gần trùng nhau. Quyết định mức phơi ra riêng. (§4.2.1)
3. **Viết mô tả theo khuôn**: khi nào dùng, không làm được gì, ví dụ tham số cụ thể, shape kết quả,
   chi phí, 1–5 ví dụ gọi. (§4.2.2)
4. **Bảo đảm trung thực tham số.** Tool làm đúng những gì tham số nhìn thấy nói; mọi chuẩn hóa đều
   được ghi lại và phản hồi lại; test bằng fixture như dấu ngoặc kép cong và ký tự ngoài ASCII.
   (§4.2.3)
5. **Coi MCP server và skill nhập về là chuỗi cung ứng**: review mô tả và nội dung, ghim phiên bản,
   cấp credential quyền tối thiểu. (§4.3)
6. **Lên kế hoạch cho việc số tool tăng**: nhóm phân tầng, nạp theo nhu cầu (gắn vào đuôi rồi ghim),
   lọc trước bằng truy hồi, hoặc chuyển quy trình vào skills. (§4.4.1–4.4.2)
7. **Thiết kế tool nhận biết cho góc nhìn từng phần**: phân trang, `offset`/`limit`, và cắt ngắn có
   nói rõ đã cắt gì, đọc tiếp thế nào. Đánh dấu tool chỉ-đọc để cache và chạy song song. (§4.5)
8. **Chọn chiến lược đa phương thức**: input native, trích xuất ra văn bản, hoặc tool phân tích trả về
   văn bản. (§4.5.1)
9. **Xếp lớp phòng thủ cho tool thực thi**: validate fail-fast, quyền hạn, phê duyệt trước cho hành
   động không đảo ngược, kiểm chứng sau bằng phương thức khác, verify-after-write với lỗi có cấu trúc,
   lưu output đầy đủ, log từng call, idempotency key và cancel tường minh. (§4.6)
10. **Chuẩn hóa cộng tác**: primitive vòng đời cho sub-agent, nguồn input có nhãn, định dạng output cố
    định, và phê duyệt của con người có timeout và mặc định. (§4.7)

## Lỗi thường gặp

- Cắt ngắn âm thầm, khiến agent tin là đã thấy hết. (§4.5)
- "Tự sửa thông minh" input sai thay vì fail-fast. (§4.6)
- Âm thầm viết lại tham số (lớp lỗi kiểu dấu ngoặc kép cong). (§4.2.3)
- Tin mô tả tool của bên thứ ba mà không review. (§4.3)
- Mô tả một dòng khiến model phải đoán khi nào dùng tool. (§4.2.2)
