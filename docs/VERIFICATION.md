# Debug và kiểm chứng theo tình huống

Chỉ đọc phần này khi sửa bug, điều tra lỗi hoặc review. Quyết định và phạm vi hiện tại của người dùng luôn có hiệu lực; tài liệu không cấp thêm quyền.

## Sửa bug

Đọc lỗi và code liên quan, thử tái hiện, xem thay đổi gần đây. Phân biệt điều quan sát được với giả thuyết. Khi liên quan nhiều thành phần, thu thập bằng chứng tại ranh giới cần thiết. Không log secrets. Thử một giả thuyết bằng thay đổi nhỏ; nếu không đúng, đọc lại bằng chứng trước khi thử tiếp. Không bắt mọi sự cố phải theo cùng số bước hoặc số phút.

Sau sửa, chạy lại triệu chứng ban đầu hoặc tương đương tự động và test hồi quy phù hợp. Nếu chưa tái hiện được thì báo thiếu bằng chứng, không tuyên bố sửa xong chắc chắn. Chỉ thêm regression test hữu ích cho bug/hành vi cần giữ; thay đổi cơ học không cần test mô phỏng chính implementation.

## Review

Với từng acceptance và hành vi cần giữ, kiểm code/caller/test/output quyết định kết quả. Spec và comment là lời khẳng định cần kiểm. Kiểm phạm vi và giả định sản phẩm, nhất là dữ liệu/lịch sử lớn và trạng thái cũ. Với finding: nêu trigger, vị trí, hậu quả và bằng chứng; xác nhận finding trước khi sửa. Không mở rộng task, rollback thay đổi khác hoặc tự mở vòng review nhiều agent.

## Báo cáo

`work finish` nhận các check gồm `kind`, `command`, `executed`, `exit_code`, `output_excerpt`, `status`, `covers`. Tham chiếu `A1..` là acceptance theo thứ tự contract, `P1..` là preserve. Bug cần một check `kind: REPRODUCTION`. Ghi `NOT_RUN`, `SKIPPED`, `INCONCLUSIVE` với lý do khi thiếu điều kiện; `FAIL` khi kiểm tra thực thất bại.

Kết quả `VERIFIED_REPORTED`, `PARTIAL_REPORTED`, `FAILED_REPORTED` chỉ đánh giá độ đầy đủ/nhất quán của báo cáo agent, KHÔNG xác thực test đã chạy, chấp thuận của người dùng hay chứng nhận bảo mật. `tested_source_hashes` phải được thu tại thời điểm kiểm thử, không lấy hash mới để gắn vào kết quả cũ. Helper không thực thi command trong JSON.

Với contract.repositories, dùng work sources ngay trước test và tested_sources_file khi finish. Mọi write_paths/read_paths của mọi repo phải có mặt; scope digest/root/file phải khớp. Source coverage DECLARED_SCOPE_COMPLETE vẫn chỉ là footprint đã khai báo, không xác thực test hay toàn dependency. Legacy thiếu file đã đổi hoặc sibling phải là INCOMPLETE/UNKNOWN. Snapshot trước test rồi phát hiện file đổi sau test phải chạy lại phần ảnh hưởng, không gắn kết quả cũ vào snapshot mới.

Nếu source hoặc contract đổi sau kiểm thử, chạy lại phần bị ảnh hưởng và cập nhật bằng chứng. Người dùng quyết định nghiệm thu; không tự chuyển canonical lifecycle sang completed cho đẹp. Commit/push/deploy là phạm vi riêng.

Resume/final-review đọc verification gần nhất từ lịch sử PROGRESS, giữ binding của chính lần kiểm đó. Checkpoint tiến độ mới không xóa báo cáo và không làm mới hash kiểm thử cũ. Xem freshness riêng của reported_verification: CURRENT/STALE/UNBOUND/UNKNOWN; không dùng freshness của tiến độ để suy ra test cũ còn hiệu lực. Báo cáo thiếu hoặc save thất bại không tạo kết luận mới.
