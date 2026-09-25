# Ch01 — Bắt đầu: Agent = Model + Harness

> Bản dịch cho người đọc của [ch01](../../book-guide/ch01-getting-started.md). Bản tiếng Anh là bản chuẩn.

**Sách:** [Chương 1 — AI Agent Bắt đầu](../../ai-agent-book/ch01-getting-started.md) · PDF trang 20–51

## Tóm tắt chương

1. **Agent = LLM + context + tools** — bộ não, đôi mắt, tay chân; thiếu một cũng không được (§1.1,
   §1.4). Trong production, **Agent = Model + Harness**, và harness gồm quản lý context, giao diện
   tool, ràng buộc, kiểm chứng và hiệu chỉnh (§1.2). Phần lớn code harness trong production hiện
   thực các cơ chế bảo đảm — ràng buộc, kiểm chứng, hiệu chỉnh — chứ không chỉ context và tools (§1.4).
2. **Khi giữ nguyên model, đòn bẩy chính là không gian quan sát và hành động** (§1.1.1). Nhiều vấn đề
   "cần model thông minh hơn" thực ra là vấn đề giao diện: đưa dữ liệu còn thiếu vào context, hoặc
   phơi thao tác còn thiếu thành tool. Mở rộng theo nhu cầu, kèm kiểm soát truy cập và kiểm chứng.
3. **Nguyên tắc thiết kế tool** (§1.1.2): năng lực đa dụng cho việc kết hợp và khám phá; tool hẹp,
   được kiểm toán cho thao tác rủi ro cao (thanh toán, xóa, deploy). Agent chạy lâu được cấp một thư
   mục làm việc ảo có kiểm soát, giới hạn theo đường dẫn, kích thước và loại file — không bao giờ là
   file system của máy chủ.
4. **Context = prefix tĩnh + trajectory** (§1.1.4–1.1.5). Prefix tĩnh là system prompt và định nghĩa
   tool; trajectory là các message user, assistant và tool. Thí nghiệm cắt bỏ cho thấy: không có kết
   quả tool thì agent thử lại mù quáng tới hết ngân sách; không có định nghĩa tool thì nó bịa ra câu
   trả lời một cách tự tin. "Đưa ra được câu trả lời" không phải là "hoàn thành nhiệm vụ".
5. **Vòng ReAct** (§1.1.5): suy nghĩ → hành động → quan sát. Các call độc lập trong một turn có thể
   chạy song song. Điểm thoát: tool trả lời cuối, response không có tool call, lỗi không khôi phục
   được, hoặc chạm giới hạn số vòng.
6. **Từ prompt engineering đến loop engineering** (§1.2.1). Code harness chỉ để vá điểm yếu của model
   (mẹo few-shot, sửa JSON, viết lại prompt) sẽ dần bị model tốt hơn hấp thu (§1.2.4.1).
7. **Ba nguyên tắc** (§1.2.2): giữ đơn giản; minh bạch (plan, log, dấu vết quyết định); thiết kế giao
   diện agent–máy tính sao cho không thể dùng sai (poka-yoke).
8. **Chọn model** (§1.2.3): đánh giá trên chính task của mình; model reasoning cho việc nhiều bước;
   tốc độ output quan trọng vì nó nhân với số vòng; đa phương thức khi task cần.
9. **Điều phối** (§1.2.4): prompt → workflow → agent tự chủ, theo đúng thứ tự áp dụng đó, và kết hợp
   — node tất định cho bước quan trọng về tuân thủ, tự chủ ở chỗ đường đi còn mở.
10. **Guardrail ba tầng, xếp theo độ khó bị vượt qua** (§1.2.5): tầng context (phân loại mức liên
    quan và an toàn, phát hiện prompt injection, gắn nhãn nguồn), tầng thực thi (xếp hạng rủi ro
    từng tool, phê duyệt của con người nằm ngoài context của model, kiểm tra output) và tầng dữ liệu
    (enforce không phụ thuộc vào model). Đo cả tỉ lệ từ chối nhầm, không chỉ số tấn công bị chặn.
11. **Con người trong vòng lặp** (§1.2.5.2): chuyển cho người khi vượt ngưỡng lỗi hoặc trước thao tác
    rủi ro cao.
12. **Năm mẫu thiết kế xuyên suốt** (§1.3): Proposer–Reviewer (một context riêng đánh giá sản phẩm),
    progressive disclosure, append-only, boundary set + retention set, minimal diff + có thể hoàn tác.

## Các bước áp dụng

1. **Giao mỗi trách nhiệm của harness cho một chủ sở hữu.** Context, tools, ràng buộc, kiểm chứng và
   hiệu chỉnh mỗi thứ có một module; kiểm chứng và hiệu chỉnh là hạng nhất, không phải làm thêm sau.
   (§1.2, §1.4)
2. **Chẩn đoán giao diện trước khi đổ lỗi cho model.** Khi agent thất bại, hỏi xem thiếu dữ liệu (thêm
   vào context) hay thiếu thao tác (thêm tool). (§1.1.1)
3. **Cấp cho agent một workspace có kiểm soát.** Giới hạn theo đường dẫn, kích thước file, số file và
   loại file; không bao giờ phơi file system của máy chủ. (§1.1.2)
4. **Xây vòng ReAct với điểm thoát rõ ràng.** Xử lý mọi tool call trong một turn, chạy song song các
   call chỉ-đọc độc lập, và dừng khi có câu trả lời cuối, lỗi không khôi phục được hoặc chạm giới hạn
   số vòng. (§1.1.5)
5. **Định nghĩa terminal state cho run** — ví dụ done, needs input, stopped at limit, failed — để bên
   gọi không bao giờ nhầm "đưa ra được câu trả lời" với "hoàn thành nhiệm vụ". (§1.1.4–1.1.5)
6. **Áp dụng tự chủ theo thứ tự.** Tối ưu prompt trước, rồi thêm node workflow, rồi mới tới tự chủ;
   giữ các bước quan trọng về tuân thủ ở dạng tất định. (§1.2.4, §1.2.4.1)
7. **Gắn nhãn code lớp thích ứng.** Đánh dấu code chỉ để vá điểm yếu của model, để gỡ bỏ khi model đã
   tự làm được. (§1.2.4.1)
8. **Giữ đơn giản và minh bạch.** Log plan và dấu vết quyết định theo từng vòng; thiết kế tool sao cho
   không thể dùng sai, chứ không chỉ là khuyên đừng dùng sai. (§1.2.2)
9. **Chọn model trên chính task của mình.** Đo tỉ lệ thành công nhiều bước, tốc độ output × số vòng,
   và đa phương thức khi cần. (§1.2.3)
10. **Đặt guardrail ba tầng.** Gắn nhãn và sàng lọc những gì vào context; xếp hạng rủi ro tool và để
    phê duyệt nằm ngoài context của model; enforce luật dữ liệu bằng code mà model không vượt qua
    được. Theo dõi cả tỉ lệ từ chối nhầm. (§1.2.5)
11. **Chuyển cho con người** sau nhiều lần lỗi liên tiếp hoặc trước thao tác rủi ro cao. (§1.2.5.2)
12. **Dùng năm mẫu thiết kế làm từ vựng chung** trong tài liệu thiết kế, để các thiết kế sau tham
    chiếu thay vì suy luận lại. (§1.3)

## Lỗi thường gặp

- Coi một câu trả lời tự tin là đã hoàn thành nhiệm vụ. (§1.1.4–1.1.5)
- Để chính context đã tạo ra sản phẩm tự duyệt nó — tự review không đáng tin. (§1.3)
- Nhảy thẳng tới agent tự chủ trong khi một workflow là đủ. (§1.2.4)
- Vá bảo mật trước khi phát hành thay vì thiết kế nó từ dòng code đầu tiên. (§1.4)
