# Ch02 — Context engineering

> Bản dịch cho người đọc của [ch02](../../book-guide/ch02-context-engineering.md). Bản tiếng Anh là bản chuẩn.

**Sách:** [Chương 2 — Context Engineering](../../ai-agent-book/ch02-context-engineering.md) · PDF trang 52–103

## Tóm tắt chương

1. **API của model là stateless; harness dựng lại context ở mỗi lần gọi** (§2.1–2.2). Việc cốt lõi
   của nó là quản lý một danh sách message. Quyết định tối thiểu cho mỗi lần gọi (§2.2.5) là
   `messages = [stable_prefix] + trajectory + [status_message]`, và chỉ nén bằng chứng cũ khi sắp hết
   ngân sách — nhưng vẫn giữ quyết định, ràng buộc, thất bại và nguồn trích dẫn.
2. **Ba quy tắc KV cache** (§2.3), được chương coi là ràng buộc kiến trúc chứ không phải tối ưu làm
   sau (§2.3.4):
   1. không bao giờ đổi system prompt hay định nghĩa tool sau khi đã cố định — đổi một byte là vô
      hiệu mọi thứ phía sau (không timestamp, không field theo user, không sắp xếp lại tool theo tần
      suất dùng);
   2. thông tin động luôn gắn vào cuối, không bao giờ chèn gần đầu;
   3. dùng định dạng message chuẩn — không tự nối các turn thành chuỗi, không đặt kết quả tool trong
      message `user`.
   Các anti-pattern đã được đo: system prompt động, thứ tự tool động, history dạng cửa sổ trượt (vừa
   phá prefix vừa đánh rơi kết quả tool mà agent cần về sau, khiến nó lặp lại việc gọi tool), và
   transcript dạng văn bản.
3. **Chat template khác nhau ở cách giữ reasoning trước đó** (§2.3.1). Có họ model bỏ nó đi, có họ
   bắt gửi lại mỗi khi có tools. Gắn nhầm kết quả tool thành `user` khiến template của Qwen3 coi đó là
   một lượt user mới và bỏ reasoning đang dở.
4. **Prompt engineering** (§2.4): Markdown cho phân cấp, thêm thẻ XML cho các phần cần máy đọc chính
   xác; quy trình kiểu SOP tốt hơn danh sách luật phẳng (xáo trộn cách tổ chức luật làm tỉ lệ thành
   công giảm hơn 30%; bỏ mô tả tool làm lỗi gọi tool tăng 45%); luật nghiệp vụ phải tường minh và
   quyết định được; ví dụ few-shot chỉ dùng khi luật không diễn đạt được mục tiêu, lấy từ một tập cố
   định theo loại task để prefix ổn định (§2.4.5).
5. **Định nghĩa tool** (§2.4.6) mang ranh giới sử dụng, ví dụ cụ thể, gợi ý hiệu năng và quan hệ giữa
   các tool ("đọc trước khi sửa"). Nạp tool trì hoãn thì gắn schema vào đuôi và cần model được huấn
   luyện cho việc đó.
6. **Prompt injection** (§2.4.7): bọc nội dung bên ngoài trong thẻ nguồn
   (`<external_content source="webpage">`), giữ vai trò message nghiêm ngặt, coi việc làm sạch chỉ là
   phụ trợ. Skill và status bar cũng là bề mặt injection — review skill của bên thứ ba như review code.
7. **Agent Skills là progressive disclosure** (§2.5): tầng 1 là metadata (`name`, và `description`
   viết như điều kiện định tuyến — "dùng khi / không dùng khi"); tầng 2 là body `SKILL.md`, nạp khi
   cần và gắn tại điểm gọi; tầng 3 là file tham chiếu, đọc có chọn lọc. Một skill hữu ích nêu rõ người
   đọc, 3–5 nguyên tắc cốt lõi có ví dụ đúng/sai, danh sách điều cấm và tài liệu tham chiếu (§2.5.2).
8. **Status bar của agent** (§2.6): trạng thái runtime tính bằng code và gắn vào đuôi — bộ đếm tool
   call, plan TODO, lỗi chi tiết, dữ kiện môi trường. Attention truy hồi tốt nhưng không tổng hợp;
   một status tính sẵn giúp model open nhỏ tiến gần độ chính xác của model hàng đầu và cắt token
   thinking khoảng một bậc độ lớn. Thông báo lỗi chi tiết (loại lỗi, tham số, gợi ý khắc phục) nâng tỉ
   lệ tìm được cách giải thay thế từ 60% lên 95%.
9. **Nén có ba động cơ** (§2.7.1): độ dài và chi phí, chất lượng suy luận, và "lo âu context". Context
   rot làm giảm khả năng truy hồi từ rất lâu trước khi cửa sổ đầy. Compaction trong production có
   nhiều tầng (§2.7.4): ngân sách cho kết quả tool → bỏ nhiễu → xóa ở tầng API → tóm tắt theo vòng
   được lưu trữ → compaction toàn phần bằng LLM đặt sau circuit breaker.
10. **Cách ly context bằng sub-agent** (§2.7.6) ngăn nhiễu đi vào context chính ngay từ đầu.

## Các bước áp dụng

1. **Dựng lại context tường minh ở mỗi lần gọi** gồm prefix ổn định + trajectory + message trạng
   thái; harness sở hữu danh sách này. (§2.2.5)
2. **Đóng băng prefix.** System prompt và định nghĩa tool không đổi trong một session: không
   timestamp, không field theo user, thứ tự tool tất định. (§2.3.2, §2.3.4)
3. **Chỉ gắn nội dung động vào đuôi** — văn bản truy hồi, skill được nạp, trạng thái. (§2.3.2)
4. **Dùng định dạng message chuẩn.** Kết quả tool nằm ở role `tool` kèm `tool_call_id`; không bao giờ
   tự dựng transcript. (§2.2.3, §2.3.1)
5. **Kiểm tra chat template của model** xem reasoning trước đó được giữ thế nào, và round-trip
   reasoning đúng cách template mong đợi. (§2.3.1)
6. **Viết system prompt như một SOP.** Section có tên, heading Markdown, khối gắn thẻ XML, luật nghiệp
   vụ tường minh và quyết định được; few-shot chỉ khi luật không đủ, lấy từ tập cố định.
   (§2.4.2–2.4.5)
7. **Viết định nghĩa tool đầy đủ**: ranh giới sử dụng, ví dụ, gợi ý hiệu năng, quan hệ với tool khác.
   (§2.4.6)
8. **Gắn thẻ nguồn cho nội dung bên ngoài và giữ vai trò nghiêm ngặt.** Review skill bên thứ ba như
   review code trước khi nạp. (§2.4.7)
9. **Hiện thực skills theo progressive disclosure.** Catalog (name + description dạng điều kiện định
   tuyến) nằm trong prefix; body nạp khi cần ở đuôi; tài liệu tham chiếu đọc có chọn lọc.
   (§2.5.1–2.5.4)
10. **Thêm status bar tính bằng code** ở đuôi: bộ đếm, plan, lỗi, dữ kiện môi trường. Không bao giờ
    xóa context gốc mà nó tóm tắt; chọn thay mới mỗi vòng hay chỉ nối thêm theo quy tắc hòa vốn.
    (§2.6.1–2.6.4)
11. **Làm lỗi tool thật chi tiết**: loại lỗi, tham số gây lỗi, một dòng gợi ý khắc phục. (§2.6)
12. **Compaction nhiều tầng khi số đo cho thấy cần.** Đưa output tool lớn ra ngoài kèm bản xem trước
    và chuỗi thay thế cố định; nén theo lô khi gần ngưỡng (ví dụ 80%); giữ quyết định, ràng buộc,
    thất bại và nguồn; đánh dấu nội dung đã nén để không bao giờ nén lần hai. (§2.7.4–2.7.5)
13. **Để agent ghi tiến độ ra tài liệu** để compaction không làm mất các quyết định ban đầu. (§2.7.5)
14. **Cách ly các subtask nhiều nhiễu trong context của sub-agent.** (§2.7.6)

## Lỗi thường gặp

- System prompt hoặc thứ tự tool động — lần gọi nào cũng trượt cache. (§2.3)
- History dạng cửa sổ trượt: phá prefix và đánh rơi kết quả tool agent vẫn cần. (§2.3)
- Đặt kết quả tool trong message `user`. (§2.3.1)
- Chỉ nén vì độ dài mà bỏ qua context rot. (§2.7.1)
- Danh sách luật phẳng, không có tổ chức trong system prompt. (§2.4.3)
