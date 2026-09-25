# Ch09 — Sự tiến hóa liên tục của agent

> Bản dịch cho người đọc của [ch09](../../book-guide/ch09-continuous-agent-evolution.md). Bản tiếng Anh là bản chuẩn.

**Sách:** [Chương 9 — Sự tiến hóa liên tục của Agent](../../ai-agent-book/ch09-continuous-agent-evolution.md) · PDF trang 355–375

## Tóm tắt chương

1. **Lưu kinh nghiệm không phải là học từ nó** (phần mở đầu chương). Việc học chỉ xảy ra sau khi hệ
   thống đánh giá, so sánh giữa các trajectory, khái quát hóa và kiểm chứng. Phản hồi production không
   phải tín hiệu sạch: hài lòng không có nghĩa là tuân thủ. Con đường thực tế hiện nay là một hệ thống
   học có thể kiểm chứng bao quanh model (§9.4).
2. **Đánh giá trước khi đúc kết** (§9.1): ba tầng verifier — kết quả (test, trạng thái database), quy
   trình (luật, quyền, chuỗi hành động) và chất lượng (rubric có bằng chứng và nêu độ bất định). Tầng
   càng thấp càng phải dựa vào code và sự thật nền.
3. **Bốn vật mang cho một cập nhật**, chọn theo cách năng lực được biểu diễn tốt nhất (§9.2):
   - **tài liệu tri thức** — dữ kiện, kinh nghiệm, ngoại lệ, nguồn: trajectory thô → phân tích từng run
     → khái quát xuyên trajectory; một luật cần ít nhất hai trajectory ủng hộ không thất bại và phải
     chuyển được sang task rời rạc (§9.2.1);
   - **prompt và skill** — phán đoán diễn đạt được bằng lời, cập nhật bằng diff tối thiểu có nguồn gốc
     và được test trên boundary set đã thất bại và retention set đã thành công (§9.2.2);
   - **chương trình và harness** — quy trình tất định và ràng buộc cứng với kiểm tra trước hành động,
     sau hành động và trạng thái cuối; vòng đời `candidate → validated → invalid`; mỗi thay đổi là một
     change contract có thể bác bỏ (§9.2.3);
   - **tham số** — nhận biết, văn phong, chiến lược ngầm (§9.2.4, xem ch08).
   Một năng lực thường trải trên nhiều vật mang.
4. **Ví dụ — skill làm rõ yêu cầu** (§9.2.2.2) phải cân bằng giữa hỏi quá ít (làm lại) và hỏi quá nhiều
   (tra hỏi). So sánh "làm luôn", "hỏi rồi làm" và "hỏi, xác nhận một spec ngắn, rồi làm", phân tầng
   theo rủi ro và độ mơ hồ. Chỉ số: trôi yêu cầu, làm lại sau bàn giao, số vòng làm rõ, thời gian tới
   output hữu ích đầu tiên, tỉ lệ bỏ cuộc, tỉ lệ sửa spec. Skill lo việc hỏi và giải thích; harness lo
   việc chặn các thao tác ghi rủi ro cao chưa được xác nhận.
5. **Hai vòng lặp** (§9.3): thực thi online chỉ ghi bằng chứng; tiến hóa offline tổng hợp, chẩn đoán,
   đề xuất ứng viên và phát hành sau khi kiểm chứng. Tách "cập nhật harness" (có đề xuất được thay đổi
   tốt không?) khỏi "lợi ích của harness" (agent có nạp và làm theo không?).
6. **Giới hạn của vòng kiểm chứng được** (§9.3.1): với công việc mở, giữ lại kết quả âm tính, tách
   khẳng định khỏi bằng chứng, giữ sự đa dạng trong tìm kiếm, và để con người định nghĩa vấn đề và tiêu
   chí đánh giá.
7. **Ranh giới an toàn** (§9.3.2): bằng chứng không tin cậy không bao giờ được ghi thẳng vào chỉ dẫn;
   ứng viên không bao giờ phục vụ traffic thật trước khi kiểm chứng; agent không được sửa verifier,
   test, ngưỡng phát hành, audit log của chính nó, hay bản ổn định dùng để duyệt nó.
8. **Hợp nhất offline — "học trong giấc ngủ"** (§9.3.3): kích hoạt, định hướng, thu thập và hợp nhất,
   kiểm chứng, cắt tỉa và lập lại chỉ mục; cho hết hạn các luật bị bằng chứng mới bác bỏ; giữ prompt
   toàn cục nhỏ bằng cách chuyển luật cục bộ vào skill của domain.

## Các bước áp dụng

1. **Kiểm chứng run trước khi học từ nó**, ở ba tầng: kết quả, quy trình, chất lượng. (§9.1)
2. **Chọn vật mang theo bản chất của năng lực** — tri thức, prompt/skill, chương trình/harness hay tham
   số — và chấp nhận rằng có thay đổi trải trên nhiều vật mang. (§9.2)
3. **Chỉ nâng một luật thành tri thức khi có bằng chứng**: ít nhất hai trajectory ủng hộ không thất bại,
   và phải chuyển được sang task rời rạc. (§9.2.1)
4. **Sửa prompt và skill bằng diff tối thiểu có nguồn gốc**, test trên boundary set đã thất bại và
   retention set đã thành công. (§9.2.2)
5. **Đánh giá tường minh chính sách làm rõ yêu cầu**: so sánh làm luôn, hỏi-rồi-làm và
   hỏi-xác-nhận-rồi-làm theo độ mơ hồ và rủi ro, với chỉ số trôi yêu cầu, làm lại và số vòng; để skill
   hỏi còn harness chặn. (§9.2.2.2)
6. **Viết change contract có thể bác bỏ cho mọi thay đổi harness**: bằng chứng, nguyên nhân gốc nghi
   ngờ, thành phần, tác động dự đoán, hồi quy có thể xảy ra, test cho cả hai. (§9.2.3)
7. **Tách vòng online khỏi vòng offline**, và đo cả việc thay đổi tốt có được đề xuất không lẫn việc
   chúng có được nạp và làm theo không (tỉ lệ kích hoạt và tuân thủ). (§9.3)
8. **Bảo vệ gốc tin cậy**: không có gì tự động được sửa verifier, test, ngưỡng, audit log hay bản dùng
   để duyệt; ứng viên tránh xa traffic thật cho tới khi được kiểm chứng. (§9.3.2)
9. **Hợp nhất định kỳ**: gộp, kiểm chứng, cắt tỉa, lập lại chỉ mục, cho hết hạn luật bị bác bỏ, chuyển
   luật cục bộ vào skill của domain. (§9.3.3)
10. **Để con người định nghĩa vấn đề và tiêu chí đánh giá** cho các task mở. (§9.3.1)

## Lỗi thường gặp

- Coi sự hài lòng hay chấp thuận của user là tín hiệu học sạch. (phần mở đầu chương, §9.1)
- Biến một lần thành công thành luật. (§9.2.1)
- Ghi bằng chứng không tin cậy thẳng vào chỉ dẫn. (§9.3.2)
- Để chính hệ thống đang được cải thiện tự sửa verifier của nó. (§9.3.2)
