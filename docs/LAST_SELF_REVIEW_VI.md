# KẾT QUẢ TỰ REVIEW CUỐI — BẢN PRACTICAL 3.0

**Ngày:** 29/10/2026 · **Mục tiêu:** phát hiện trùng lặp, sai tuyên bố năng lực, side effects và trở ngại sử dụng thực tế trước bàn giao.

## 1. Đối chiếu phạm vi

- Không thêm UI/app mới; dùng chính Codex/Claude Desktop hoặc terminal CLI.
- Không thay đổi EA01–EA16 trong đợt này; SI01–SI14 kế thừa, giữ nguyên gap native.
- Chỉ thêm module `agentflow_runtime/practical.py`, các lệnh CLI nhỏ, cải tiến installer và tests/docs.
- Không bắt user tự nhập Task ID hoặc chạy công cụ cho mỗi tin nhắn; `resume` theo tên là tùy chọn cho agent.
- Không tự chuyển model, không tạo trusted approval, không thực thi provider, không sửa product code trong kit.

## 2. Kiểm tra kỹ thuật

- Installer default `STRICT`, `ADVISORY` phải chủ động chọn; `--apply` mới ghi hai managed blocks.
- Chuyển mode/version phải `--upgrade`; không ghi đè managed blocks tùy chỉnh.
- Rollback kiểm tra SHA-256 hiện tại với bản sau cài và backup SHA-256; từ chối nếu có xung đột.
- Uninstall không xóa nội dung tùy chỉnh ngoài managed blocks; không để file rỗng khi được tạo hoàn toàn bởi kit.
- `resume` chỉ auto chọn task khi chắc chắn; không tự tạo task khi mơ hồ; `handoff` có dữ liệu snapshot chưa xác thực.
- `repo-status` chỉ chạy Git read-only, nếu thất bại không giả định working tree sạch.
- `final-review` không chuyển UNVERIFIED evidence thành PASS/DoD.
- Positive test harness không được coi là chứng cứ malware/hard enforcement native.

## 3. Kết quả thực nghiệm

- 312/312 unittest mới + kế thừa PASS; 5/5 Preview PASS.
- 9/9 scratch checks baseline PASS.
- 20/20 scratch E2E mới PASS và source fixture giữ nguyên (bản `release/PRACTICAL_SMOKE.json`).
- Các lượt test chạy trên Linux, không mở app Codex/Claude, không có Mac runtime attestations. Có một lượt test runner gọi subprocess bị chậm bất thường; cần test lại trên Mac.

## 4. Những gì chưa thể ký xác nhận

- Enforced Strict Approval trong hai GUI và hai CLI.
- Ranh giới ghi Mac ngăn shell/patch/MCP bypass, trusted writer, real multiwriter & Git index.
- Actual user-chat provenance và user identity verification.
- Native installer theo app build và GUI/CLI E2E.
- Mức cải thiện hiệu suất, usability thực tế, hiệu quả context/usage chưa có dữ liệu.

## 5. Đề xuất reviewer tiếp nhận

Bắt đầu bằng chạy onboarding trên **một repo giả** rồi làm **một Quick task**, đo số thao tác thật và quan sát agent có đọc instructions không. Báo ngắn các blocker được chứng minh và phương án tối thiểu. Không mở rộng hệ thống trước khi trình và nhận phản hồi từ người dùng.
