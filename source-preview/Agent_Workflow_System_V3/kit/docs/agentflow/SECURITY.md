# Security & giới hạn thực thi trên macOS — ĐỌC TRƯỚC

## Phân biệt yêu cầu và mức bảo đảm thực tế

**D1-B:** User muốn code không thể bị sửa trước khi duyệt. Bộ kit đã triển khai **phê duyệt gắn hash, chặn tại PreToolUse, từ chối những shell commands không allowlist**. Điều này chặn lỗi thông thường trên các tool được hook. **Chưa chứng minh hard security** trên cả Codex Desktop, Claude Desktop và CLI của user.

**D3-B:** User muốn nhiều session ghi đồng thời, cùng working tree. Bộ kit đã triển khai **SQLite transaction + lease trên đường dẫn file**; không đủ để ngăn mọi xung đột logic, file được ghi ngoài hook, hoặc các tiến trình đồng thời qua shell ngoài bộ kiểm soát.

## Threat model

Hai ứng dụng cùng chạy dưới cùng một tài khoản macOS (UID) và có quyền ghi trực tiếp vào repo. File hooks, scripts, approval DB và source code đều có thể được chỉnh bởi tiến trình có cùng quyền nếu không dùng biện pháp OS-level riêng. **Không dùng database/hook hash như bằng chứng chống một agent cố tình lách hoặc bị prompt injection nghiêm trọng**. Hook cũng có thể không chạy vì chưa trust, bị disable, command not found, failure/timeout hoặc specialized tool path khác.

## Guardrails hiện có

- Contract được validate trước khi propose. `open_questions` không rỗng thì không duyệt.
- Approval gắn với hash của contract và bản SPEC hiển thị; sửa sau duyệt sẽ chặn.
- Mỗi `UserPromptSubmit` không phải Duyệt/Tiếp tục đưa session về PREFLIGHT.
- Trước khi duyệt, file edit chỉ được phép cho `contract.json` của task.
- Sau duyệt, ghi ngoài `scope` bị chặn trên file tools đã hook.
- Quyền ghi file có lease theo session, giải phóng ở PostToolUse hoặc SessionEnd; stale lease tự hết sau 120 giây.
- Shell mặc định deny những câu lệnh thay đổi hệ thống. Chỉ một số lệnh read-only và các lệnh controller được kiểm tra.
- Verification chạy theo cấu hình, dùng lock global nếu không còn writer lease hoạt động.

## Rủi ro chưa được giải quyết

1. Shell command có thể che side effects sau lệnh con hoặc chương trình gọi. Regex/allowlist không phải sandbox.
2. Một số tool không qua hook: agent hoặc plugin có thể ghi ngoài sự kiểm soát.
3. SQLite/file lease không ngăn logic conflict giữa hai file khác nhau; không có 2-phase merge hay dependency graph.
4. Git index/branch/HEAD là shared state; không được để các agent tự commit/reset/checkout.
5. Lease có TTL, phiên làm việc lâu hoặc hook PostToolUse không chạy có thể bị stale/race. Cần nâng cấp heartbeat/lock semantics để vận hành production.
6. User gõ “Duyệt” qua chat là xác nhận trong giao diện có hook, **không phải chữ ký danh tính chống giả mạo ở cấp OS**.
7. Model có thể tự đánh giá scope sai; user cần đọc contract trước duyệt.
8. Chạy các bài test có side effects, watch mode, build/formatter có thể sửa repo; cấu hình verify phải review theo project và không chạy cùng writer.

## Điều kiện nếu sau này cần cưỡng chế mạnh

Cần sandbox/permission boundary thật, ví dụ chạy CLI trong môi trường có quyền file system khác hoặc write broker tách quyền và apply patch sau khi phê duyệt, cùng cơ chế tích hợp GUI chấp nhận được. Trên macOS, **không mặc định sandbox-exec** là giải pháp ổn định (cơ chế cũ/deprecated); cần thẩm định theo phiên bản macOS và app. Nếu chính GUI không hỗ trợ tách quyền, hard guarantee có thể yêu cầu thay đổi cách khởi chạy hoặc chấp nhận mức hook guardrail.

Đừng triển khai bộ kit ở chế độ Bypass Permissions. Trước khi dùng repo có dữ liệu quan trọng, hoàn thành acceptance tests với chính Codex Desktop, Claude Desktop, Codex CLI và Claude CLI.
