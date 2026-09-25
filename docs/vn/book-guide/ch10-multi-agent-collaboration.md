# Ch10 — Cộng tác đa agent (và lời bạt)

> Bản dịch cho người đọc của [ch10](../../book-guide/ch10-multi-agent-collaboration.md). Bản tiếng Anh là bản chuẩn.

**Sách:** [Chương 10 — Nhiều lần cộng tác Agent](../../ai-agent-book/ch10-multi-agent-collaboration.md) · PDF trang 376–417 ·
[Lời bạt](../../ai-agent-book/postscript.md) · PDF trang 418–421

## Tóm tắt chương

1. **Hai trục thiết kế** (§10.1): context dùng chung hay cách ly, và tô-pô — ngang hàng (2–3 agent lặp
   với nhau), manager/orchestrator, bàn giao phi tập trung. Các agent cách ly giao tiếp qua tham số
   tool, file system dùng chung hoặc message bus.
2. **Tiêu chí duy nhất** (§10.2): đa agent chỉ có ích khi cộng tác mang lại thông tin mà một lần sinh
   đơn lẻ không thể có — kết quả thực thi, screenshot đã render, kiểm chứng bên ngoài. Cùng một model
   tự review hay tranh luận trên cùng một văn bản không thêm được gì, thậm chí còn hại, khi cùng lượng
   tính toán. Một run đa agent tốn gấp nhiều lần token của một cuộc chat (khoảng 15×).
3. **Đổi vai trong một context** (§10.3): ưu tiên skills (prefix tĩnh giữ nguyên, `SKILL.md` gắn vào
   đuôi) khi các vai khác nhau về tri thức hay quy trình; chỉ dùng agent riêng khi các vai khác nhau về
   quyền hạn hoặc tác dụng phụ, và enforce giới hạn tool bằng code.
4. **File system ảo với bốn vùng** (§10.4.1): scratchpad riêng, workspace dùng chung (có kiểm soát đồng
   thời), tài nguyên bên ngoài được mount (chủ yếu chỉ-đọc) và tài nguyên chỉ-đọc dựng sẵn (skills,
   template). Truyền đường dẫn, không truyền nội dung.
5. **Mặt phẳng điều khiển** (§10.4.2): phong bì message có cấu trúc; trạng thái qua file tiến độ thay
   vì toàn bộ trajectory; phát hiện treo theo thời gian sửa đổi; hủy nhẹ nhàng rồi cưỡng bức, lan xuống
   các agent con; ngân sách, chọn model theo task, giới hạn đồng thời.
6. **Loop engineering và Proposer–Reviewer** (§10.4.3): lỗi phổ biến nhất là kết thúc quá sớm — "xong"
   cho có, bỏ cuộc sau một hướng, thành công giả. "Done" là một lời khẳng định cho tới khi verifier
   chứng minh: model được đề xuất done nhưng không được tự duyệt. Reviewer đọc bằng chứng độc lập
   (test, trạng thái, screenshot), trả về phát hiện có thể hành động, và không được sửa test, bộ thu
   thập bằng chứng hay cổng phát hành. Tự sửa khi không có phản hồi bên ngoài làm giảm độ chính xác.
7. **Mẫu manager** (§10.4.4): planner là nút thắt, nên nó nhận model và prompt mạnh nhất; manager chỉ
   giữ một chỉ mục các sản phẩm; kết quả song song được chốt theo "thành công đã kiểm chứng đầu tiên",
   nhận một cách idempotent.
8. **Bàn giao phi tập trung** (§10.4.5): gói bàn giao gồm mục tiêu, ràng buộc, dữ kiện đã chấp nhận,
   tham chiếu sản phẩm, ngân sách còn lại và các agent đã ghé; runtime lo phát hiện vòng lặp và ngân
   sách.
9. **Các kiểu lỗi** (§10.5): mất cập nhật trên file dùng chung (§10.5.1), lỗi khuếch đại dọc chuỗi
   (§10.5.2), hội tụ đồng dạng — cùng model, cùng lỗi (§10.5.3), đùn đẩy trách nhiệm (§10.5.4), vòng lặp
   mất kiểm soát (§10.5.5), và nợ hiểu biết của những người vận hành hệ thống (§10.5.6). Lỗi của agent
   sai mà nghe hợp lý, nên chỉ phản hồi bên ngoài tất định mới đáng tin.
10. **Lời bạt**: Agent = LLM + context + tools. Harness bù cho những gì model chưa làm được một cách
    đáng tin, và bị gỡ dần từng lớp khi model tự nắm được các ràng buộc đó — nhưng mỗi biên giới mới lại
    cần một lớp mới. Hãy luôn hỏi: agent nhìn thấy gì, làm được gì, và "làm đúng xong" được kiểm chứng
    thế nào?

## Các bước áp dụng

1. **Mặc định là một agent.** Chỉ thêm agent khi nó mang lại thông tin mới (kết quả thực thi,
   screenshot, kiểm tra bên ngoài), và so với agent đơn ở cùng ngân sách token. (§10.2)
2. **Quyết định mô hình context và tô-pô** — dùng chung hay cách ly; ngang hàng, manager hay phi tập
   trung. (§10.1)
3. **Đổi vai bằng skills** khi các vai khác nhau về tri thức; chỉ tách agent khi khác quyền hạn hoặc
   tác dụng phụ, với giới hạn enforce bằng code. (§10.3)
4. **Chia file system thành bốn vùng** và truyền đường dẫn, không truyền nội dung. (§10.4.1)
5. **Xây mặt phẳng điều khiển**: phong bì có cấu trúc, file tiến độ, phát hiện treo, hủy lan xuống agent
   con, ngân sách và giới hạn đồng thời tường minh. (§10.4.2)
6. **Biến "done" thành một trạng thái được kiểm chứng**: model đề xuất, verifier duyệt; reviewer đọc
   bằng chứng độc lập và không được sửa các cổng kiểm soát. (§10.4.3)
7. **Nếu dùng manager**, cho nó model và prompt mạnh nhất, giữ chỉ mục sản phẩm, và chốt việc song song
   theo thành công đã kiểm chứng đầu tiên. (§10.4.4)
8. **Chuẩn hóa gói bàn giao**: mục tiêu, ràng buộc, dữ kiện đã chấp nhận, tham chiếu sản phẩm, ngân
   sách, các agent đã ghé. (§10.4.5)
9. **Phòng các kiểu lỗi**: optimistic locking hoặc working copy cách ly chống mất cập nhật, kiểm chứng
   chéo từ bằng chứng gốc chống khuếch đại lỗi, đa dạng nguồn chống hội tụ đồng dạng, ngân sách và hủy
   tường minh chống vòng lặp mất kiểm soát. (§10.5)
10. **Giữ cho con người hiểu được hệ thống** — tài liệu ngắn, cập nhật giúp chống nợ hiểu biết.
    (§10.5.6)
11. **Xem lại từng lớp harness khi model tiến bộ**; gỡ những gì model đã tự làm được. (lời bạt)

## Lỗi thường gặp

- Coi việc cùng một model tranh luận hay tự review là kiểm chứng. (§10.2)
- Chấp nhận "done" của model mà không có bằng chứng độc lập. (§10.4.3)
- Ghi đồng thời vào workspace dùng chung mà không có khóa. (§10.5.1)
- Thêm agent chỉ để có thêm agent, và trả giá gấp nhiều lần token. (§10.2)
