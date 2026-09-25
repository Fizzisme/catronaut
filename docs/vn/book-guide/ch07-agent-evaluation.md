# Ch07 — Đánh giá agent

> Bản dịch cho người đọc của [ch07](../../book-guide/ch07-agent-evaluation.md). Bản tiếng Anh là bản chuẩn.

**Sách:** [Chương 7 — Đánh giá Agent](../../ai-agent-book/ch07-agent-evaluation.md) · PDF trang 254–299

## Tóm tắt chương

1. **Đối tượng được đánh giá là model + harness** (§7.1). Model-swap test (giữ harness, thay model
   mạnh hơn hoặc yếu hơn) tách nút thắt của harness khỏi nút thắt của model; ablation (giữ model, tắt
   một thành phần harness) đo giá trị của thành phần đó. Có bộ eval thì team áp dụng model mới trong
   vài giờ thay vì dựa vào cảm tính.
2. **Chỉ số** (§7.2):
   - Pass@k (ít nhất một trong k lần thành công) đo trần năng lực; Pass^k (cả k lần thành công, không
     dính veto) đo độ tin cậy nghiệp vụ — với p = 0,6 thì Pass@5 ≈ 99% nhưng Pass^5 ≈ 7,8%
     (§7.2.1–7.2.2);
   - chỉ số quy trình: tỉ lệ hành động hợp lệ, độ chính xác gọi tool, hiệu quả đường đi, độ phủ truy
     hồi, chi phí và latency (§7.2.3);
   - an toàn và tuân thủ là veto item, độ bền vững, và phủ cả trajectory lẫn kết quả — "agent nói đã
     đặt chỗ" không phải là "chỗ đã được đặt" (§7.2.4);
   - lấy mẫu kiểm tra bằng người và hiệu chuẩn judge trên tập chuẩn (ví dụ Cohen's κ > 0,7) trước khi
     tin LLM judge ở quy mô lớn; thêm case đối kháng (§7.2.5).
3. **Môi trường đánh giá** (§7.3) là dataset + trạng thái môi trường reset được + tool nguyên tử +
   rubric + giao thức chạy. Môi trường dạng tool kiểm chứng bằng thực thi và trạng thái; môi trường
   tương tác người–máy dùng user simulator tiết lộ thông tin dần dần và kiên nhẫn có hạn.
4. **Thiết kế dataset** (§7.4): rõ ràng vs mở, thực tế vs kiểm soát, đa dạng có gắn nhãn năng lực,
   chi phí vs độ phủ, chống contamination (template có tham số, canary, độ mới); mô tả task chính xác
   với điều kiện thành công máy kiểm tra được; phân cấp độ khó; trap task; kiểm chứng kép FAIL_TO_PASS +
   PASS_TO_PASS; kiểm soát chất lượng chặt.
5. **LLM-as-a-judge** (§7.5.1) với rubric dựa trên chuyên gia, đầy đủ, có trọng số (thiết yếu / quan
   trọng / tùy chọn / veto) và kiểm tra độc lập được. Đề phòng thiên lệch độ dài, thiên lệch vị trí và
   reward hacking; ưu tiên judge từ nhiều họ model; judge đa phương thức dùng được cho screenshot UI.
6. **Quy trách nhiệm thất bại** (§7.5.2): với mỗi trajectory thất bại, ghi bước không chấp nhận được
   đầu tiên, loại lỗi, nguyên nhân gốc vs hệ quả, khả năng khôi phục và độ tin cậy. Taxonomy khởi đầu
   cho coding agent gồm hiểu sai yêu cầu, thiếu quy trình, lỗi gọi tool, gian lận kiểm chứng, thay đổi
   chưa trọn, báo cáo sai với user, suy giảm phi chức năng, kết thúc bất thường và dừng quá sớm. Lọc
   trước bằng luật, định vị bằng LLM sau.
7. **Task hồi quy** (§7.5.3): task đầu-cuối bảo vệ cả luồng; task tiền tố trajectory đóng băng trạng
   thái ngay trước một lỗi đầu tiên đã biết và chấp nhận một tập hành động kế tiếp hợp lệ (cùng một tập
   hành động bị cấm). So sánh theo cặp để xếp hạng hệ thống (§7.5.4).
8. **Chọn model** (§7.6): TTFT vs tốc độ decode, latency của thinking, đuôi p95, chi phí mỗi task, chỉ
   số Pass và đường cong năng lực theo ngân sách; đo ngưỡng hành động mặc định của model (đọc thêm hay
   sửa sớm); đo các đòn bẩy chi phí cùng nhau — mức tiết kiệm không cộng dồn.
9. **Thống kê** (§7.7): SE ≈ √(p(1−p)/n) — với n = 100 thì 70% ± 9 điểm; phân tích paired (McNemar,
   paired bootstrap), nhiều seed, hiệu chỉnh cho so sánh nhiều lần.
10. **Observability** (§7.8): trace dạng cây span; lỗi production, sau khi ẩn danh, quay về bộ eval.
11. **Từ báo cáo tới cải tiến** (§7.9): khi điểm thay đổi, kiểm tra hệ thống đánh giá trước; mỗi vòng
    chỉ đổi một biến; thắng trên subset nhỏ chỉ đổi được quyền chạy lớn hơn.
12. **Hạ tầng eval nội bộ** (§7.10): mọi tính năng lớn bật/tắt độc lập được để ablation; A/B test tách
    chỉ số cơ chế khỏi chỉ số mục tiêu và giữ chỉ số guardrail; system prompt sau khi render được
    snapshot theo phiên bản, và chạy lại bộ eval mỗi khi prompt đổi.
13. **Môi trường mô phỏng** (§7.11) là cầu nối giữa đánh giá và huấn luyện: verifier trở thành hàm
    reward, nhưng huấn luyện cần thêm ngữ nghĩa reset và yêu cầu thông lượng.

## Các bước áp dụng

1. **Đánh giá model và harness cùng nhau**, chạy model-swap test và ablation để tìm nút thắt.
   (§7.1, §7.10.1)
2. **Báo Pass@k cho trần năng lực và Pass^k cho độ tin cậy**, kèm chỉ số quy trình, chi phí và latency;
   biến vi phạm an toàn thành veto item; kiểm chứng trạng thái kết quả, không chỉ trajectory.
   (§7.2.1–7.2.4)
3. **Hiệu chuẩn mọi LLM judge** với nhãn của người trước khi dựa vào nó; thêm case đối kháng.
   (§7.2.5, §7.5.1)
4. **Dựng môi trường reset được**: dataset, trạng thái, tool nguyên tử, rubric, giao thức chạy; thêm
   user simulator cho task có hỏi user. (§7.3.1–7.3.3)
5. **Thiết kế dataset**: điều kiện thành công máy kiểm tra được, phân cấp độ khó, trap task, chống
   contamination, kiểm tra FAIL_TO_PASS và PASS_TO_PASS. (§7.4)
6. **Viết rubric có trọng số và veto item**, đề phòng thiên lệch độ dài và vị trí; dùng judge đa
   phương thức cho output hình ảnh. (§7.5.1)
7. **Ghi hồ sơ quy trách nhiệm cho mỗi run thất bại**: bước sai đầu tiên, loại, nguyên nhân gốc, bằng
   chứng. (§7.5.2)
8. **Biến lỗi thành task hồi quy**, cả đầu-cuối lẫn tiền tố trajectory. (§7.5.3)
9. **Chọn model theo chi phí mỗi task và đường cong năng lực theo ngân sách**, không theo một điểm số;
   đo các đòn bẩy chi phí cùng lúc. (§7.6)
10. **Nêu rõ n, seed và khoảng tin cậy**, và dùng kiểm định paired. (§7.7)
11. **Trace run dạng cây span** và đưa lỗi production quay về bộ eval. (§7.8)
12. **Khi điểm thay đổi, kiểm tra hệ thống đánh giá trước**, rồi đổi từng biến một. (§7.9)
13. **Cho mọi tính năng lớn của harness bật/tắt được**, snapshot system prompt đã render theo phiên
    bản, và chạy lại bộ eval mỗi khi prompt đổi. (§7.10)
14. **Coi verifier là hàm reward tương lai** khi thiết kế môi trường. (§7.11)

## Lỗi thường gặp

- Kết luận từ một lần chạy (n = 1) được trình bày như sự thật. (§7.7)
- Cộng dồn mức tiết kiệm từ các đòn bẩy riêng lẻ. (§7.6)
- Tin một judge chưa được hiệu chuẩn. (§7.2.5)
- Chấp nhận "agent nói đã làm" mà không kiểm tra trạng thái kết quả. (§7.2.4)
- Điểm benchmark giảm bị đổ cho agent trong khi chính hệ thống đánh giá đã thay đổi. (§7.9)
