# Ch03 — Bộ nhớ người dùng và cơ sở kiến thức

> Bản dịch cho người đọc của [ch03](../../book-guide/ch03-memory-and-knowledge-base.md). Bản tiếng Anh là bản chuẩn.

**Sách:** [Chương 3 — Bộ nhớ người dùng và cơ sở kiến thức](../../ai-agent-book/ch03-memory-and-knowledge-base.md) · PDF trang 104–143

## Tóm tắt chương

1. **Hai quy mô tri thức bền vững**: bộ nhớ người dùng (một người, xuyên session) và kho tri thức
   dùng chung (mọi người). Cùng cơ chế, cùng kiểu lỗi: xung đột, dữ kiện cũ, truy hồi thiếu chính xác.
   (§3.1, §3.4)
2. **Phân cấp bộ nhớ** (§3.1.2): trajectory (bản ghi chỉ-thêm của một session), bộ nhớ dài hạn (được
   viết lại, hợp nhất, cắt tỉa) và business state (giai đoạn task do developer định nghĩa, ví dụ "cần
   làm rõ / đang làm / xong") là những thứ khác nhau.
3. **Bốn định dạng lưu trữ** (§3.1.3), từ rẻ tới giàu: simple notes, advanced notes, JSON cards,
   advanced JSON cards. Thẻ giàu hợp với dữ kiện nhỏ và quan trọng; ghi chú đơn giản hợp với khối
   lượng lớn. User-as-Code (§3.1.4) đi xa hơn: state có kiểu cùng các hàm luật tất định để đếm, phát
   hiện xung đột và kiểm tra ràng buộc.
4. **Đánh giá bộ nhớ trước khi thiết kế nó** (§3.1.1): ba cấp — nhớ cơ bản, truy hồi xuyên session,
   phục vụ chủ động — chấm trên một tập case cố định.
5. **Nền tảng RAG** (§3.2): chia khối theo cấu trúc là mặc định trong production (bắt đầu 256–1024
   token, chồng lấn 10–20%, rồi tinh chỉnh theo chất lượng truy hồi đo được); embedding dày đa ngôn
   ngữ cộng BM25 thưa; truy hồi kết hợp → hợp nhất RRF → rerank bằng cross-encoder; chỉ số recall@k,
   MRR, nDCG.
6. **Tập case thô không phải là tri thức** (§3.3). Top-k trên nhiều case riêng lẻ không đếm được
   chúng, và không case nào tự nêu ranh giới chính sách. Chắt lọc lúc lập chỉ mục thành các thẻ luật
   nêu rõ phạm vi và ngoại lệ.
7. **Lập chỉ mục có cấu trúc** (RAPTOR, GraphRAG; §3.3.1) chỉ khi truy vấn cần tổng hợp nhiều tài liệu
   hoặc điều hướng nhiều cấp; còn lại truy hồi kết hợp là đủ.
8. **Mô hình file system** (§3.3.2): tri thức là file Markdown trong Git, gồm tóm tắt L0 (~100
   token), tổng quan L1 (~2K) và toàn văn L2 nạp khi cần, cộng liên kết chéo và trang index tường minh.
9. **Cập nhật tri thức** (§3.3.3) là pull request: bên đề xuất soạn diff tối thiểu kèm bằng chứng,
   một bên review độc lập đối chiếu với bằng chứng gốc, CI kiểm tra, và chỉ bản đã merge mới dựng lại
   chỉ mục dẫn xuất. Bằng chứng, tri thức và phục vụ là các tầng tách biệt; nội dung bị thay thế được
   đánh dấu; quyền được lọc ở tầng truy hồi; tenant được cách ly.
10. **Agentic RAG** (§3.3.4): truy hồi như một tool trong vòng lặp tốt hơn truy hồi một lần với câu
    hỏi phức tạp; truy hồi một lần vẫn nhanh hơn và tốt ngang với câu hỏi đơn giản. Văn bản truy hồi
    mang theo prompt injection gián tiếp — gắn thẻ nguồn và không bao giờ để nó kích hoạt hành động có
    tác dụng phụ.
11. **Contextual retrieval** (§3.3.5): thêm vào đầu mỗi khối một dòng ngữ cảnh do LLM viết trước khi
    embedding (giảm 49% lỗi với BM25, 67% với rerank).
12. **Bộ nhớ hai tầng** (§3.3.5, §3.4): một bản tổng quan có cấu trúc, nhỏ, luôn nằm trong context,
    cộng truy hồi chi tiết chính xác khi cần.

## Các bước áp dụng

1. **Tách ba loại state.** Giữ trajectory ở dạng chỉ-thêm, giữ bộ nhớ dài hạn được chọn lọc, và lưu
   business state (giai đoạn task, quyết định, câu trả lời đã có) cạnh sản phẩm — không chỉ trong
   lịch sử chat. (§3.1.2)
2. **Viết phần đánh giá bộ nhớ trước**: nhớ, truy hồi xuyên session và phục vụ chủ động trên tập case
   cố định. (§3.1.1)
3. **Chọn định dạng lưu trữ theo mức quan trọng**: thẻ giàu cho dữ kiện nhỏ quan trọng, ghi chú đơn
   giản cho khối lượng lớn, state có kiểu và hàm luật khi cần đếm hoặc xử lý xung đột. (§3.1.3–3.1.4)
4. **Bắt đầu tri thức dưới dạng file system.** Markdown trong Git với tóm tắt ~100 token, tổng quan,
   toàn văn khi cần, liên kết chéo và mỗi thư mục một trang index, đọc bằng các file tool thông
   thường. (§3.3.2)
5. **Chắt lọc, đừng đổ đống.** Biến tập case thành thẻ luật có phạm vi và ngoại lệ rõ ràng trước khi
   cho truy hồi; giữ case gốc làm bằng chứng. (§3.3)
6. **Khi cần RAG, đi đúng pipeline**: khối theo cấu trúc 256–1024 token, chồng lấn 10–20%, dense +
   BM25, RRF, rerank bằng cross-encoder, đo bằng recall@k, MRR và nDCG trên tập truy vấn cố định.
   (§3.2.1–3.2.4)
7. **Thêm tiền tố contextual retrieval** cho các khối. (§3.3.5)
8. **Phơi truy hồi thành tool** cho câu hỏi phức tạp, giữ truy hồi một lần cho câu hỏi đơn giản, và
   gắn nhãn văn bản truy hồi là không tin cậy. (§3.3.4)
9. **Giữ một bản tổng quan có cấu trúc, nhỏ trong context** và lấy chi tiết khi cần. (§3.3.5, §3.4)
10. **Coi thay đổi tri thức là pull request** có bằng chứng và review độc lập; chỉ dựng lại chỉ mục
    dẫn xuất từ nội dung đã merge; đánh dấu các mục bị thay thế. (§3.3.3)
11. **Enforce quyền ở tầng truy hồi**, cách ly tenant, và xóa dữ liệu cá nhân khỏi log. (§3.3.3, §3.1.8)
12. **Chỉ dùng RAPTOR hay GraphRAG** khi truy vấn thực sự cần tổng hợp nhiều tài liệu. (§3.3.1)

## Lỗi thường gặp

- Lập chỉ mục case thô rồi mong bộ truy hồi đếm được hay khái quát được. (§3.3)
- Ghi bộ nhớ mà không kiểm tra nguồn, thời gian, xung đột và quyền riêng tư. (§3.4)
- Chỉ giữ business state trong lịch sử chat, nên nó bị mất hoặc bị mâu thuẫn. (§3.1.2)
- Để văn bản truy hồi kích hoạt hành động có tác dụng phụ. (§3.3.4)
