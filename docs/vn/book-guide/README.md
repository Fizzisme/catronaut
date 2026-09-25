# Book guide — *Hiểu sâu về AI Agent* (bản tiếng Việt)

> Bản dịch cho người đọc của [docs/book-guide/](../../book-guide/README.md). Bản tiếng Anh là bản chuẩn.

Tóm tắt theo từng chương những gì sách khuyến nghị, chuyển thành các bước để xây dựng harness cho
agent, kèm tham chiếu mục (§) về sách. Bản thân cuốn sách nằm ở
[docs/ai-agent-book/](../../ai-agent-book/README.md). Khi guide và sách khác nhau thì theo sách.

Mỗi guide có ba phần:

- **Tóm tắt chương** — lập luận của chương, rút gọn, kèm tham chiếu §.
- **Các bước áp dụng** — checklist đánh số: làm gì, vì sao, sách nói ở đâu.
- **Lỗi thường gặp** — những gì chương cảnh báo.

Các guide không gắn với dự án cụ thể. [ROADMAP](../ROADMAP.md) nối mỗi milestone với các chương mà
nó dựa vào.

| Chương | Guide | Các bước chính |
|---|---|---|
| 1 Bắt đầu | [ch01](ch01-getting-started.md) | Coi harness là sản phẩm; vòng ReAct có điểm thoát rõ ràng; prompt → workflow → tự chủ; guardrail ba tầng |
| 2 Context engineering | [ch02](ch02-context-engineering.md) | Prefix ổn định, phần động ở đuôi; system prompt kiểu SOP; skills theo progressive disclosure; status bar; compaction nhiều tầng |
| 3 Bộ nhớ và cơ sở kiến thức | [ch03](ch03-memory-and-knowledge-base.md) | Tách trajectory, memory và business state; knowledge dạng file system trước RAG; chắt lọc case thành luật; cập nhật có review |
| 4 Công cụ | [ch04](ch04-tools.md) | Chọn hình thức cho năng lực; mô tả tool đầy đủ; trung thực tham số; cắt ngắn tường minh; phòng thủ nhiều lớp cho tool thực thi |
| 5 Coding agent | [ch05](ch05-coding-agents-and-code-generation.md) | Read/write/edit/glob/grep; edit khớp chính xác; phân loại lỗi và khôi phục theo tầng; bắt đầu từ ví dụ đã kiểm chứng; render rồi review |
| 6 Tương tác | [ch06](ch06-interaction-observation-and-action-spaces.md) | Sự kiện có cấu trúc; safe point và cancel; tool bất đồng bộ; đánh giá hoàn thành bằng quan sát mới |
| 7 Đánh giá | [ch07](ch07-agent-evaluation.md) | Đánh giá model + harness; Pass^k và veto; judge được hiệu chuẩn; quy trách nhiệm lỗi; thống kê; feature switch |
| 8 Post-training | [ch08](ch08-model-post-training.md) | Loại trừ cách sửa không cần train; SFT cho giao thức, RL cho chính sách; chỉ dùng dữ liệu đã kiểm chứng; LoRA mặc định; thiết kế reward |
| 9 Tiến hóa liên tục | [ch09](ch09-continuous-agent-evolution.md) | Đánh giá trước khi đúc kết; chọn đúng vật mang; boundary và retention set; vòng tiến hóa offline; bảo vệ gốc tin cậy |
| 10 Đa agent + lời bạt | [ch10](ch10-multi-agent-collaboration.md) | Chỉ thêm agent khi có thông tin mới; done phải được kiểm chứng; bàn giao có cấu trúc; chống xung đột và lỗi đồng dạng |

## Tìm một mục trong sách

Bản chuyển sang Markdown của sách bị mất vài heading. Một số mục xuất hiện dưới dạng dòng in đậm thay
vì heading (ví dụ §2.4.1–2.4.4, §2.3.5, §8.1.3, §9.2.2.2, §9.3.1), còn §6.3 và §8.3 không có dòng
heading riêng. Hãy tìm số mục trong file của chương. Khi bản chuyển đổi có vẻ sai, bản PDF là chuẩn.
