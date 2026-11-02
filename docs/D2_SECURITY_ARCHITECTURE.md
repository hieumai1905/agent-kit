# Đ2 — Security Architecture & Threat Model

**Trạng thái:** DEVELOPMENT PROTOTYPE; G2 **BLOCKED / NOT_CERTIFIED**. Chưa có sản phẩm Trusted Approval hay Enforced Multi-Writer chạy trên macOS.

## 1. Ranh giới của phần đã xây

- `agentflow_security.approvals`: tạo challenge có thời hạn cho Task Contract `WAITING_APPROVAL`, xác minh chữ ký Ed25519 được ràng buộc với `repo_id`, `task_id`, `contract_revision`, `contract_sha256`, challenge, issuer, mục đích và thời gian; dùng SQLite transaction để chống dùng lại challenge. Kết quả `SIGNATURE_VALID_UNCERTIFIED`; task vẫn `WAITING_APPROVAL`, **không** có execution grant.
- `agentflow_security.gates`: phân loại lệnh shell theo tác dụng phụ ở mức bảo thủ; hiển thị khả năng ứng dụng/CLI và mặc định `DENY` mọi yêu cầu ghi vì chưa có chứng nhận OS. Trường `claimed_host_certification` hoặc policy text từ agent không được dùng để cấp quyền.
- `agentflow_security.mutation_lab`: chứng minh thuật toán *cooperative* compare-hash/atomic-replace, khóa tệp, kiểm tra đường dẫn/symlink/hardlink và chống ghi đè stale trên thư mục **tạm**. Không phải mutation broker; không cung cấp CLI sửa source thật.
- `tools/mac_capability_probe.py`: đọc thông tin OS, sự hiện diện của CLI, Info.plist của application bundle nếu có; KHÔNG gọi model và không sửa repo, ứng dụng hoặc cấu hình. `NOT_CERTIFIED` kể cả chạy trên macOS.
- `agentflow_core.schema` v3: `approval_challenges`, `verified_approval_receipts`. Không thêm cột boolean `approved=true` đáng tin cậy. Bản ghi chữ ký phải được xác minh lại bởi trusted component; DB cùng UID không phải nguồn tin cậy.

## 2. Threat model tối thiểu

| Đối tượng/đường tấn công | Nguy cơ | Cách giảm thiểu cần chứng minh ở G2 |
|---|---|---|
| Agent sửa SQLite/control JSON cùng UID | Tự tạo approval, grant, policy | Control plane/trust roots phải ở realm không cho agent ghi; không dùng DB flag làm quyền |
| Agent đọc private signing key | Tự ký receipt | Private key bên ngoài agent process/FS, UI có xác minh human presence |
| Agent giả mạo `"Duyệt"` hoặc hook event | Social-engineering authority | Chat chỉ là dữ liệu; phê duyệt qua kênh xác thực đáng tin cậy |
| Hook thất bại/bị tắt/bỏ qua | Tool chạy ngoài gate | Cưỡng chế độc lập ở OS/mandatory write broker, kiểm tra từng đường ghi |
| Agent gọi shell, editor, MCP, build script | Ghi trực tiếp | Hạn chế toàn bộ đường ghi / dùng process sandbox được chứng nhận |
| Agent cố sử dụng quyền của người dùng trong desktop GUI cùng UID | Vượt khóa ứng dụng | Phân tách identity/capability hiệu lực; yêu cầu proof trên đúng ứng dụng/build |
| Symlink/hardlink/path traversal | Ghi ngoài scope | Dirfd/no-follow, theo dõi inode, giới hạn mount, kiểm tra trước ghi; test race |
| TOCTOU giữa check và apply | Ghi đè thay đổi session khác | Compare-and-apply nguyên tử cùng ranh giới khóa/fencing được tin cậy |
| Zombie session sau khi lease hết hạn | Ghi trễ | Per-writer fencing epochs và chứng minh dừng/quyền bị thu hồi |
| Git index / test DB / build cache chung | Trộn diff/test artifacts | Điều phối tài nguyên và test isolation |
| Replay receipt từ repo/spec cũ | Duyệt sai version | Nonce một lần, thời hạn, binding repo/task/spec/action/issuer |
| Provider update thay đổi behavior | Giảm coverage | Chứng nhận theo OS build + app build; downgrade trạng thái khi cập nhật |

**Lưu ý quan trọng:** SQLite `chmod 0600`, hash audit, chữ ký hợp lệ và hooks không đủ nếu agent và control plane chia sẻ UID/quyền filesystem. Receipt ký bởi khóa do agent tự đưa vào cấu hình cũng không đáng tin. Chỉ các thành phần thực sự được cách ly khỏi agent mới được phép phát hành quyền.

## 3. Ranh giới quyền được đề xuất cho bản production

```text
Trusted human UI (human presence attested)
          │
          ▼
Trusted Approval Authority (private key protected)
          │  receipt cryptographically bound to task + spec + action
          ▼
Trusted Control Plane (privileged/isolated boundary)
          │  checks capability, session identity, revocation, scopes,
          │  file/resource lease + evidence freshness
          ▼
Mandatory Mutation Broker / OS-enforced sandbox
          │  atomic compare-and-apply + post-write reconciliation
          ▼
Repository working tree
```

`Codex/Claude` agent là tiến trình **untrusted** đối với quyết định bảo mật. Adapter/hook gửi yêu cầu, không được tự quyết định/cấp quyền. Việc chọn kiến trúc protected service hoặc OS sandbox cụ thể còn chờ thực nghiệm macOS.

## 4. Cơ chế phê duyệt phải phân tách

- `TASK_APPROVAL` chỉ cho phép triển khai đúng Task Contract, không tự tạo quyền ghi.
- `SESSION_ACTIVATION` cần phiên đã xác minh và môi trường hợp lệ.
- `WRITE_AUTHORIZATION` cần scope, current file version, resource fencing và mandatory OS enforcement.
- `POLICY_ADMIN`, `GIT_COMMIT`, `PUSH`, `DEPLOY`, `PRODUCTION_MIGRATION` cần intents/permissions riêng; không suy diễn từ TASK_APPROVAL.
- Thu hồi quyền: hệ thống phải thử dừng mọi đường ghi thực tế, không chỉ cập nhật cờ trong SQLite.

## 5. Kết quả đã và chưa chứng minh

**Đã thử trên Linux container:** signature verification; challenge replay/expiry/misbind rejection; default deny; tool effect hints; algorithm compare-and-replace trên temp fixtures; migrations/transactions từ Đ1.

**Chưa chứng minh:** UI phê duyệt có human presence đáng tin, key management OS-protected, socket/peer identity phân biệt agent với người duyệt, mandatory OS write sandbox, toàn bộ GUI tool paths, khả năng chặn khi hooks lỗi, multi-writer trong working tree thật, crash fencing native macOS.

**Quy tắc phát hành:** G2 chỉ được PASS sau khi các negative native tests đạt với đúng mỗi surface/build được quảng bá. Nếu chỉ đạt mức Coordinated, status phải là `NOT_CERTIFIED_FOR_STRICT_MODE`, không đổi yêu cầu người dùng.
