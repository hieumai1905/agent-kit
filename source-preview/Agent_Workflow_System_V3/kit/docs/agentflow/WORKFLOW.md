# Workflow đã chốt — Repo-centric Strict Approval

## Nguyên tắc

- Người dùng chỉ nhập yêu cầu tự nhiên trong app/terminal.
- Codex/Claude do người dùng chọn. Không tự chuyển nền tảng.
- Mọi yêu cầu sửa code đều trải qua READ-ONLY PREFLIGHT → SPEC → HUMAN REVIEW → APPROVAL → EXECUTION.
- Dữ liệu dùng chung trong repo: `REQUEST.md` (yêu cầu gốc), `contract.json` (hợp đồng máy đọc), `SPEC.md` (bản hiển thị chờ duyệt), `STATE.md` (checkpoint).
- Trạng thái approval, session và leases nằm ở SQLite local. `approved` được kiểm tra bằng content hash của cả JSON và bản hiển thị SPEC. Bất cứ chỉnh sửa nào sau duyệt làm mất quyền thực thi.

## 1. Khi người dùng nhập prompt mới

Hook `UserPromptSubmit` tạo Task ID và `REQUEST.md` nếu session chưa có task. Nếu session đã gắn task và nhận một yêu cầu tự nhiên mới, lượt đó quay về PREFLIGHT. Một câu hỏi đọc-only không cần sửa spec. Thay đổi phạm vi bắt buộc revise/propose/duyệt lại. Các câu `Duyệt` và `Tiếp tục T-ID` là tín hiệu được nhận diện riêng.

## 2. Preflight

Agent khảo sát repo với các lệnh đọc-only, điền `contract.json` (đúng trường). `open_questions` phải rỗng trước khi `propose`; nếu thiếu quyết định sản phẩm thì hỏi user. Không dùng placeholder/giả định không được gắn nhãn. Tự đề xuất risk, complexity, scope dựa trên code và rủi ro; user không khai báo thủ công.

## 3. Propose

Agent gọi `python3 .agentflow/bin/agentflow.py propose T-...`, tool render `SPEC.md` và chốt SHA-256. Agent **phải hiển thị toàn bộ SPEC** cho người dùng, không chỉ viết “đã chuẩn hóa”. User phản hồi `Duyệt` nếu chấp thuận; sửa lại nếu không.

## 4. Human approval

`UserPromptSubmit` nhận chính xác `Duyệt` trong session đang có task và proposed fingerprint hợp lệ. Nếu `SPEC.md` hoặc `contract.json` thay đổi, approval không hợp lệ. Mọi thay đổi ngoài scope phải quay lại PREFLIGHT. Đây là việc chấp thuận phạm vi code, không tự động cho phép deploy, migrate, commit, push hoặc lệnh hủy dữ liệu.

## 5. Execution

Ưu tiên thay đổi tập trung, đúng scope. `PreToolUse` kiểm tra path ghi, lease và session mode. Ghi `STATE.md` sau mốc có ý nghĩa; không tạo log từng tool call. Kiểm chứng bằng `verification.json` thực sự đã được cấu hình; không nói PASS nếu chưa chạy.

## 6. Parallel sessions

Nhiều session cùng repo được phép làm task độc lập. Các thao tác ghi có đường dẫn xác định dùng lease SQLite; cùng file sẽ tranh chấp, khác file có thể thực hiện. Shell side-effect mặc định bị chặn; bài test được cấu hình chạy qua `verify` có khóa global. Git operations không được tự thực hiện. Đây là **phối hợp mức hook, không phải hard isolation**.

## 7. Session rollover

Đổi Codex↔Claude **do user quyết định**. Session mới: `Tiếp tục T-ID`; nếu có đúng một task mở, chỉ cần `Tiếp tục`. Agent mới đọc SPEC, STATE, git status/diff, code thực tế; điều chỉnh checkpoint khi tài liệu cũ không khớp.

## 8. Model Advisor

`model-advice T-ID --provider claude|codex` trả `FAST/BALANCED/DEEP`, và danh sách model cụ thể **chỉ khi** chúng được ghi nhận là available + allowed trong model-policy. `UNKNOWN` usage không được giả là thoải mái. Agent chỉ đề xuất; user đổi model từ app/CLI khi đồng ý.
