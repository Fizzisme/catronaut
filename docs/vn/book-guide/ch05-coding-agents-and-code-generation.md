# Ch05 — Coding agent và tạo mã

> Bản dịch cho người đọc của [ch05](../../book-guide/ch05-coding-agents-and-code-generation.md). Bản tiếng Anh là bản chuẩn.

**Sách:** [Chương 5 — Coding Agent và tạo mã](../../ai-agent-book/ch05-coding-agents-and-code-generation.md) · PDF trang 170–214

## Tóm tắt chương

1. **Agent đa dụng = coding agent + file system** (§5.1.1–5.1.2). Một coding agent tối thiểu cần bảy
   tool: code interpreter, shell, read, write, edit, glob, grep. File system là xương sống của agent:
   bộ nhớ, sản phẩm và kinh nghiệm đều nằm trong file.
2. **File chỉ dẫn của project** (`CLAUDE.md`, `AGENTS.md`) là context cấp project rẻ nhất và ổn định
   cache nhất (§5.1.3).
3. **Quy trình khuyến nghị** (§5.1.3): hiểu project → làm rõ yêu cầu → viết thiết kế ngắn và xin duyệt
   cho việc không tầm thường → hiện thực → kiểm chứng (test pass, chứ không phải "đã viết code") → tự
   review → giữ tài liệu đồng bộ. Việc đơn giản có thể đi tắt.
4. **Harness cho coding** (§5.1.4) có bốn phần: chuẩn nghiệm thu, ranh giới thực thi, tín hiệu phản
   hồi và phương tiện khôi phục. Nguyên tắc: ràng buộc hơn chỉ dẫn, kiểm chứng tự động, phản hồi
   nhanh có cấu trúc, khôi phục đáng tin cậy (version control, snapshot). Ràng buộc cả quy trình — cấm
   đường tắt phá hoại như ghi đè một file chưa từng đọc. Coding agent trưởng thành vì hàng chục năm
   test suite, hệ thống kiểu và version control đã sẵn là một harness mạnh (§5.3).
5. **Sự cố và khôi phục** (§5.1.5):
   - bốn tầng lỗi — API (429, quá tải, timeout, output bị cắt), tool (tool ảo, tham số sai, lặp cùng
     một lỗi), context (tràn, compaction thất bại, tool call/kết quả không thành cặp), luồng điều
     khiển (vòng lặp chết, vòng xoáy tử thần);
   - phân loại trước khi đếm: retryable hay không; fingerprint tool + tham số để phát hiện lặp; bộ
     đếm lỗi liên tiếp theo từng đường;
   - watchdog theo dõi stream còn sống; sửa tính toàn vẹn của trajectory (mỗi call có một kết quả)
     trước khi gửi;
   - khôi phục theo tầng: retry âm thầm với backoff và jitter → hạ cấp và đi tiếp (tăng giới hạn
     output, chỉ dẫn viết tiếp, model dự phòng) → chỉ báo cho user khi mọi cách đều thất bại;
   - lỗi tool trở thành input có cấu trúc cho model, không bao giờ làm sập session;
   - lưu trajectory trung lập provider — text reasoning mang đi được, còn chữ ký và call id của
     provider được sinh lại theo từng provider;
   - mọi đường khôi phục có circuit breaker; đường xử lý lỗi không bao giờ gọi lại model.
6. **Kỹ thuật hiện thực** (§5.1.6): execute tool call ngay khi tham số validate xong; call song song
   sau cờ concurrency của từng tool; đọc theo khoảng dòng có số dòng; cắt đầu + cuối và lưu output đầy
   đủ; trạng thái môi trường gắn vào đuôi; kiểm tra cú pháp ngay sau mỗi lần ghi.
7. **Tìm kiếm** (§5.1.7): grep và glob tại chỗ, không cần chỉ mục embedding.
8. **So sánh năm cách edit** (§5.1.8): diff + model apply; chuỗi cũ → chuỗi mới (chính xác, match duy
   nhất hoặc lỗi — dễ đoán nhất); số dòng (mong manh); lệnh Vim; neo đầu + cuối. Edit là thao tác cốt
   lõi của lặp và bảo trì.
9. **Bảo mật** (§5.1.9): bộ ba chết người — dữ liệu riêng tư + nội dung không tin cậy + giao tiếp ra
   ngoài — với bộ nhớ bền vững là chất khuếch đại; kiểm soát egress mạng; phân tích ngữ nghĩa lệnh;
   trung thành với chủ thể.
10. **Code là siêu năng lực** (§5.2): code làm công cụ tư duy (§5.2.1); luật nghiệp vụ dưới dạng code
    có kiểm tra phía server (§5.2.2); media được sinh qua vòng Proposer–Reviewer render sản phẩm rồi
    review bằng hình ảnh, dừng khi "đạt chất lượng" hoặc chạm giới hạn vòng (§5.2.3); code làm bộ điều
    hợp hệ thống (§5.2.4); UI được sinh ra, ví dụ form làm rõ ý định trong một lượt thay vì nhiều lượt
    (§5.2.5); agent tạo agent (§5.2.6). Sinh từ một ví dụ chất lượng cao rồi sửa tốt hơn sinh từ đầu
    (§5.2).

## Các bước áp dụng

1. **Cấp cho agent file system và các tool cốt lõi**: read, write, edit, glob, grep — cộng code
   interpreter và shell chỉ khi được phép chạy code. (§5.1.1–5.1.2)
2. **Giữ một file chỉ dẫn của project** làm context ổn định, thân thiện cache. (§5.1.3)
3. **Mã hóa quy trình**: hiểu → làm rõ → thiết kế ngắn (duyệt khi không tầm thường) → hiện thực →
   kiểm chứng → tự review → đồng bộ tài liệu. (§5.1.3)
4. **Xây bốn phần của harness**: chuẩn nghiệm thu, ranh giới thực thi, tín hiệu phản hồi và khôi phục
   (snapshot hoặc version control). Enforce ràng buộc bằng code, kể cả ràng buộc quy trình như "không
   ghi đè nếu chưa đọc". (§5.1.4)
5. **Phân loại lỗi** theo tầng (API, tool, context, luồng điều khiển) và theo khả năng retry;
   fingerprint call lặp lại; đếm lỗi liên tiếp theo từng đường. (§5.1.5)
6. **Khôi phục theo tầng**: retry lỗi retryable với backoff và jitter, rồi hạ cấp và đi tiếp, rồi mới
   báo user. Trả lỗi tool dưới dạng observation có cấu trúc. Đặt circuit breaker trên mọi đường khôi
   phục và không bao giờ gọi model từ đường xử lý lỗi. (§5.1.5)
7. **Bảo vệ trajectory**: ghép mỗi tool call với một kết quả trước khi gửi, phát hiện output bị cắt
   và không bao giờ execute call bị cắt, lưu trajectory trung lập provider. (§5.1.5)
8. **Áp dụng các kỹ thuật hiện thực**: validate rồi mới execute, cờ concurrency cho từng tool, đọc
   theo khoảng dòng có số dòng, cắt đầu + cuối và lưu output đầy đủ, trạng thái môi trường ở đuôi,
   kiểm tra cú pháp sau mỗi lần ghi. (§5.1.6)
9. **Tìm kiếm tại chỗ bằng grep và glob.** (§5.1.7)
10. **Edit bằng thay chuỗi cũ → mới chính xác**, báo lỗi rõ khi không có hoặc có nhiều match; giữ ghi
    cả file cho file mới. (§5.1.8)
11. **Kiểm tra bộ ba chết người cho mọi bộ tool**; kiểm soát egress mạng. (§5.1.9)
12. **Dùng code làm đòn bẩy**: luật dưới dạng code, render-rồi-review cho sản phẩm hình ảnh có giới
    hạn vòng, form sinh ra để làm rõ yêu cầu, và bắt đầu từ ví dụ đã kiểm chứng thay vì từ đầu.
    (§5.2.2–5.2.5, §5.2)

## Lỗi thường gặp

- Tuyên bố xong khi code đã viết nhưng chưa được kiểm chứng. (§5.1.3)
- Ghi lại cả file làm mất nội dung chưa đọc và nhân số token output; edit theo số dòng dễ vỡ. (§5.1.8)
- Retry lỗi không retry được, hoặc để handler lỗi gọi model thành vòng xoáy tử thần. (§5.1.5)
- Tool call không thành cặp bị provider từ chối. (§5.1.5)
- Ràng buộc chỉ nằm trong prompt. (§5.1.4)
