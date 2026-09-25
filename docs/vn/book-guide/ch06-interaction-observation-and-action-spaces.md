# Ch06 — Tương tác: mở rộng không gian quan sát và hành động

> Bản dịch cho người đọc của [ch06](../../book-guide/ch06-interaction-observation-and-action-spaces.md). Bản tiếng Anh là bản chuẩn.

**Sách:** [Chương 6 — Tương tác: mở rộng không gian quan sát và không gian hành động](../../ai-agent-book/ch06-interaction-observation-and-action-spaces.md) · PDF trang 215–253

## Tóm tắt chương

1. **Hai trục mới** (§6.1): phương thức (văn bản, âm thanh, màn hình, cảm biến) và thời điểm (thế giới
   đẩy sự kiện tới; hành động kéo dài qua nhiều lượt và có thể bị ngắt hoặc bị giành quyền). Model
   được huấn luyện trên dữ liệu luân phiên theo lượt; môi trường thật thì không chờ.
2. **Agent bất đồng bộ, hướng sự kiện** (§6.2):
   - mọi input là một sự kiện có cấu trúc gồm nguồn, kênh, nội dung và ngữ cảnh, để agent không bao
     giờ nhầm chỉ dẫn của user với kết quả tool — đây cũng là một lớp chống injection;
   - sự kiện chỉ được xử lý tại safe point (cuối một bước suy luận, khi tool trả về), với ba chiến
     lược: xếp hàng (gom lại ở safe point kế tiếp), hủy (tạo safe point sớm cho sự kiện khẩn) và song
     song (truy vấn nhẹ, độc lập) (§6.2.6);
   - điểm hủy phải là chỗ tool hoặc suy luận kết thúc an toàn được; kết quả tool chưa xong là một
     placeholder tường minh, không bao giờ giả làm thành công (§6.2.6);
   - thao tác dài có ngữ nghĩa tool bất đồng bộ: `initiate_x` trả về ngay một task id và kết quả tới
     sau dưới dạng sự kiện (§6.2.7);
   - sự kiện gom lô được đánh số để model không chỉ chú ý tới cái cuối cùng.
3. **Tool kích hoạt sự kiện** (hẹn giờ, theo dõi tác vụ nền, kênh bên ngoài; §6.2.3) và **tool giao
   tiếp với người dùng** (agent nhắn cho user qua các kênh thay vì trả về một lượt assistant; §6.2.4).
4. **Giọng nói** (§6.3): cascade, omni (end-to-end) hay full-duplex; tách nhanh/chậm, trong đó tiền
   cảnh giữ cuộc hội thoại còn hậu cảnh suy luận.
5. **Computer use** (§6.4): nhận biết → suy nghĩ → hành động → quan sát lại; chỉ số phần tử có cấu trúc
   tốt hơn tọa độ thô (§6.4.1–6.4.2); hiểu được màn hình không có nghĩa là hoàn thành task; sau mỗi
   hành động phải xác nhận thực tế khớp với kế hoạch.
6. **Robot** (§6.5): điều khiển phân tầng, action chunking, world model; việc hoàn thành được đánh giá
   bằng một quan sát mới, không bao giờ bằng lời tự nhận của model.
7. **Khung điều khiển chung** (§6.6): cảm nhận → phán đoán trạng thái và thời điểm → chọn → hành động
   → quan sát → tiếp tục, sửa, thử lại, dừng hoặc lập lại kế hoạch, với các primitive dùng chung: đánh
   thức, safe point, hủy, giành quyền, tách nhanh/chậm.

## Các bước áp dụng

1. **Biểu diễn mọi input thành sự kiện có cấu trúc** gồm nguồn, kênh, nội dung và ngữ cảnh. (§6.2)
2. **Chỉ xử lý sự kiện tại safe point**, và chọn xếp hàng, hủy hay song song cho từng loại sự kiện.
   (§6.2.6)
3. **Đặt điểm hủy ở chỗ công việc kết thúc an toàn được**, và báo công việc bị ngắt bằng placeholder
   tường minh — không bao giờ báo thành công. (§6.2.6)
4. **Cho thao tác dài ngữ nghĩa bất đồng bộ**: trả task id ngay và gửi kết quả sau dưới dạng sự kiện;
   để tên và mô tả tool nói rõ call là bất đồng bộ. (§6.2.7)
5. **Đánh số sự kiện gom lô** để cái nào cũng được chú ý. (§6.2)
6. **Chỉ thêm tool kích hoạt sự kiện và tool giao tiếp người dùng** khi có kênh đầu vào thật.
   (§6.2.3–6.2.4)
7. **Tách đường nhanh và chậm** cho tương tác thời gian thực: tiền cảnh phản hồi, hậu cảnh suy luận.
   (§6.3)
8. **Với agent thao tác màn hình**, hành động qua chỉ số phần tử có cấu trúc và quan sát lại sau mỗi
   hành động. (§6.4.1–6.4.2)
9. **Đánh giá hoàn thành bằng một quan sát mới**, không bao giờ bằng lời tự nhận của model. (§6.4, §6.5)
10. **Dùng lại khung điều khiển chung** và các primitive của nó cho mọi phương thức. (§6.6)

## Lỗi thường gặp

- Cho rằng thế giới sẽ chờ tới lượt của model. (§6.1)
- Giả làm thành công cho một tool bị ngắt hoặc timeout. (§6.2.6)
- Tuyên bố task xong vì đã hiểu màn hình, chứ không phải vì trạng thái đã thay đổi. (§6.4)
