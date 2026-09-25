# Ch08 — Post-training mô hình

> Bản dịch cho người đọc của [ch08](../../book-guide/ch08-model-post-training.md). Bản tiếng Anh là bản chuẩn.

**Sách:** [Chương 8 — Post-training mô hình](../../ai-agent-book/ch08-model-post-training.md) · PDF trang 300–354

## Tóm tắt chương

1. **Bốn giai đoạn, bốn khoảng trống khác nhau** (§8.1, §8.7): pre-training và mid-training cung cấp
   tri thức và năng lực nền; SFT sửa giao thức (định dạng, schema tool call, văn phong, quy trình) với
   hiệu quả mẫu cao; RL dịch chuyển xác suất về phía các chiến lược model đã thỉnh thoảng làm được.
   "SFT ghi nhớ, RL khái quát hóa" là xu hướng quan sát trong thí nghiệm có đối chứng, không phải quy
   luật (§8.16).
2. **Quyết định trước khi huấn luyện** (§8.7):
   1. loại trừ trước các cách sửa không cần đổi trọng số — prompt, tools, ràng buộc bằng code, quản lý
      context; dùng RAG cho dữ kiện hay thay đổi;
   2. đo pass@1 và pass@k trên task mục tiêu held-out — nếu pass@k ≈ 0 thì RL không có gì để khuếch
      đại (mid-train hoặc SFT trước);
   3. SFT xây giao thức, không xây kho tri thức;
   4. chỉ RL khi rollout chấm điểm được, thỉnh thoảng thành công, và reward trung thực.
3. **LoRA mặc định** (§8.1, hộp LoRA): áp LoRA lên mọi ma trận trọng số chính, kể cả MLP; learning
   rate ≈ 10× fine-tune toàn phần; rank SFT 64–256, rank RL 8–32; một inference server chứa được nhiều
   adapter.
4. **Dữ liệu SFT** (§8.5–8.6): seed của người định dạng → model thầy nhân rộng → rejection sampling chỉ
   giữ trajectory đã kiểm chứng. Pipeline: dữ liệu production → blueprint task → task tổng hợp (sinh
   lại dữ liệu cá nhân) → nhiều trajectory ứng viên → kiểm chứng task và trajectory → tập SFT.
   Trajectory thất bại không bao giờ là ví dụ tích cực; chúng thành cặp preference hoặc probe độ phủ.
5. **Môi trường và cách ly** (§8.10): độ trung thực của môi trường quan trọng hơn thuật toán RL; train
   và eval có thể dùng chung generator và verifier nhưng không bao giờ dùng chung task instance; test
   ẩn và đáp án tham chiếu nằm lại với verifier. Có thể để model mô phỏng môi trường, nhưng thiên lệch
   của nó trở thành trần của policy.
6. **RL nhiều lượt** (§8.11): phân bổ tín dụng qua các lượt; gọi tool đưa môi trường vào bên trong
   agent.
7. **Thiết kế reward** (§8.12): reward kiểm chứng được trước; kết quả trước quá trình; đề phòng reward
   hacking và reward seeking; RLVP — thưởng cho kết quả và phạt vi phạm đường đi kiểm chứng được (ví
   dụ sửa test, bỏ qua bước kiểm tra).
8. **Chưng cất** (§8.13): on-policy distillation biến một rollout thành giám sát dày theo từng token;
   tự chưng cất dùng được khi không có thầy mạnh hơn.
9. **Từ bad case tới huấn luyện** (§8.14): task hồi quy đầu-cuối → pool RL/RFT; task tiền tố trajectory
   → cặp DPO và ví dụ biên cho SFT; hồ sơ quy trách nhiệm lỗi → nhãn process reward và luật RLVP;
   rubric → vector reward. Case mẫu: kết thúc quá sớm, chuyển dấu ngoặc kép phụ thuộc phạm vi, chép
   chính xác `old_string` (§8.14.1–8.14.3).
10. **Cạm bẫy** (§8.15): huấn luyện để nhớ dữ kiện, RL khi định dạng chưa ổn định, hàm reward tồi, mô
    phỏng kém trung thực, overtraining, đánh giá thấp chi phí tính toán của RL (10–100× SFT), dữ liệu
    bẩn. Kiểm chứng giả định ở quy mô nhỏ trước khi chi lớn.

## Các bước áp dụng

1. **Làm hết các cách sửa không cần huấn luyện trước**: prompt, tools, ràng buộc bằng code, context;
   RAG cho dữ kiện hay đổi. Ghi lại những gì đã thử. (§8.7)
2. **Đo pass@1 và pass@k trên task held-out** và để chúng chọn giai đoạn: mid-training khi pass@k ≈ 0,
   SFT khi định dạng chưa ổn, RL khi rollout chấm được và đôi khi thành công. (§8.7, §8.16)
3. **Dùng SFT cho giao thức**, không phải cho tri thức. (§8.5)
4. **Bắt đầu từ LoRA mặc định**: mọi ma trận chính kể cả MLP, LR ≈ 10× fine-tune toàn phần, rank
   64–256 cho SFT và 8–32 cho RL, early stopping trên tập held-out. (§8.1)
5. **Chỉ xây dữ liệu SFT từ trajectory đã kiểm chứng**: seed → thầy → rejection sampling qua chính các
   verifier mà eval dùng; thất bại thành cặp preference, không bao giờ thành ví dụ tích cực. (§8.5–8.6)
6. **Chia train và eval theo task template**; không bao giờ dùng chung instance; giữ test ẩn ở phía
   verifier. (§8.10.3)
7. **Đầu tư vào độ trung thực của môi trường** trước khi tinh chỉnh thuật toán. (§8.10.1–8.10.2)
8. **Thiết kế reward cẩn thận**: kiểm chứng được, ưu tiên kết quả, có phạt vi phạm đường đi (RLVP).
   (§8.12)
9. **Ánh xạ tài sản eval sang mục đích huấn luyện**: hồi quy, task tiền tố, hồ sơ quy trách nhiệm và
   rubric đều có vai trò trong huấn luyện. (§8.14)
10. **Quy trách nhiệm từng tầng trước khi kết luận là lỗi model**: output tool → cách harness tuần tự
    hóa → tokenizer → output của model. (§8.14.3)
11. **Đánh giá mọi model đã huấn luyện trên boundary set và retention set**, cộng một bài kiểm tra năng
    lực tổng quát. (§8.14.1)
12. **Cân nhắc chưng cất** để tăng hiệu quả mẫu. (§8.13)
13. **Kiểm chứng ở quy mô nhỏ trước khi chi lớn.** (§8.15)

## Lỗi thường gặp

- Huấn luyện để nhớ dữ kiện vốn thuộc về truy hồi. (§8.15)
- Chạy RL khi định dạng output chưa ổn định. (§8.7, §8.15)
- Coi trajectory thất bại là ví dụ tích cực. (§8.6)
- Để train và eval dùng chung task instance. (§8.10.3)
- Đánh giá thấp chi phí tính toán của RL. (§8.15)
