# Danh sách việc cần cùng người dùng chốt sau bản nền tảng

## Đã chốt — KHÔNG hỏi lại

- macOS, cùng một thiết bị và Git repo/working tree local.
- Codex Desktop + CLI, Claude Desktop Code + CLI; người dùng chủ động chuyển nền tảng.
- Strict Approval: user phải đọc/duyệt spec trước sửa code.
- Multi-session và nhu cầu multi-writer ngay V3.0.
- Model Advisor chỉ đề xuất, phụ thuộc model được cho phép và usage; không cần subagent.
- Quality Gate theo mức rủi ro, triển khai theo repo, người dùng không khai báo task/scope thủ công.

## P0: Trước khi dùng repo thật

1. **GUI hook compatibility:** version của Codex Desktop/Claude Desktop, hoạt động và trust của `UserPromptSubmit` / `PreToolUse` / `PostToolUse` trên máy user, PATH Python3.
2. **Hard enforcement:** user yêu cầu thực sự không thể ghi code trước approval. Hook guardrail chưa đủ; xem có sandbox/OS boundary nào tích hợp được với GUI local. Nếu không, cần xác nhận giới hạn hoặc thay cách khởi chạy để đạt hard guarantee.
3. **Parallel writes:** xử lý các thao tác Shell, editor tool khác, Git, long-running processes, tác động giữa hai file khác nhau và lease expiration; thiết kế resource graph.
4. **Session routing:** cách nhận diện task mới, task phụ, sửa spec và câu hỏi trong cùng một session mà không yêu cầu user nhập lệnh.
5. **Human approval authenticity:** bảo đảm đã hiển thị đúng spec và ghi nhận đúng tác giả phê duyệt, chống giả lập qua agent process có cùng UID (yêu cầu cơ chế trusted process nếu muốn hard guarantee).

## P1: Logic nhận yêu cầu & prompting

- Thế nào là đủ thông tin để READY? Loại prompt nào tự điều tra, loại nào hỏi user?
- Cách xử lý bug chưa tìm ra nguyên nhân: được duyệt discovery phase hay cần đủ root cause?
- UI/UX specs: thiết kế tham chiếu, mức độ sáng tạo, ảnh screenshot, acceptance subjectivity.
- Phạm vi thay đổi và chiến lược task split/milestone.
- Cách phân loại confirmed/observed/assumed/unknown; tránh model bịa yêu cầu.

## P2: Logic coding sau approval

- Conventions riêng tech stack, kiến trúc/code structure, đặt tên, file size, error handling, logging.
- Test pyramid & quality metrics, review/merge/commit policies.
- UI design conventions nếu có frontend.
- Khi nào được chủ động refactor hay đổi dependency.
- Quy tắc comment/doc, readability vs performance, test coverage, accessibility.

## P3: Model routing & đo hiệu quả

- Model catalog và allowlist thực tế mỗi tài khoản.
- Usage integration và bảo toàn quota, refresh catalog.
- Mức độ escalation, review bằng model mạnh và số vòng fail.
- Evals về rework/quality, token usage, time-to-accepted-result, handoff recovery.

## V3.0 preview không nên khẳng định đã hoàn thành

- Hard OS-level sandbox cho cả hai desktop GUI.
- Hoàn toàn tự nhận diện task ngữ nghĩa và tự sinh scope đúng 100%.
- Nhiều writers an toàn tuyệt đối trên cùng shared Git working tree.
- Live usage cho cả Codex/Claude account.
- Chuyển model tự động trong same UI session.
- Code style/architecture chưa thống nhất riêng repo.
