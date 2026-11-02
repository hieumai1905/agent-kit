# G2 — Security Design Review v2: Mandatory Write Boundary (29/10/2026)

**Trạng thái: DESIGN + SCRATCH LAB. G2 = BLOCKED_NATIVE_MACOS_CERTIFICATION_REQUIRED. Không cài vào repository thật.**

## 1. Từ kết quả thực tế trên macOS

Máy người dùng: Darwin 25.6.0 arm64; Codex Desktop (`com.openai.codex` / `ChatGPT.app`), Claude Desktop, Claude CLI được phát hiện. Codex CLI chưa tìm được. Kết quả thử lab v0.1:

- Ghi trong vùng sandbox: cho phép.
- Trực tiếp ra ngoài, symlink và traversal: bị từ chối, canary không đổi.
- **Hardlink alias đặt sẵn trong thư mục cho phép: ghi thành công, canary ở ngoài cũng đổi.**

Nguyên nhân: hardlink là hai directory entries cùng trỏ tới một inode. Khi tiến trình đã được phép ghi qua tên nằm trong vùng cho phép, giới hạn đường dẫn không tự chứng minh được inode bên ngoài vẫn bất biến. **Không thể sửa bằng cách chỉ thêm prompt hoặc một rule chặn đường dẫn đặc biệt.**

Apple Secure Coding Guide khuyến nghị dùng `O_NOFOLLOW`, `fstat` và kiểm tra `st_nlink` khi mở file không đáng tin cậy. Đây là biện pháp cần thiết trong broker, nhưng **không thay thế được ngăn agent ghi trực tiếp**.

Nguồn: https://developer.apple.com/library/archive/documentation/Security/Conceptual/SecureCodingGuide/Articles/RaceConditions.html

## 2. Kiến trúc lựa chọn: Protected Control Plane + Mandatory Mutation Service

```
Bạn -> UI phê duyệt đáng tin cậy (phân biệt human và agent)
          |  receipt ràng buộc repo + task + SPEC + hành động + nonce
          v
Control Plane ngoài vùng ghi/đọc khóa của agent
    - trust anchors, revocation, policy, grants, session/capability attestation
    - thay đổi có phiên bản, resource lease + fencing + protected audit
          |  mutation intent: provider/session/repo/spec/path/before/after/epoch
          v
Trusted Mutation Service (identity / OS protection độc lập)
    1. Kiểm tra approval + session + quyền theo hành động
    2. Kiểm tra capability chứng nhận theo OS/app/build
    3. Khóa tài nguyên phù hợp; chống writer cũ (fencing)
    4. Kiểm tra nội dung, target inode, link count, ownership/mode, metadata
    5. So sánh baseline version & áp dụng thay đổi trong cùng ranh giới tin cậy
    6. Ghi audit và reconciliation, trả kết quả theo task
          |
          v
Một working tree chung (vẫn một folder cho Codex/Claude đọc)
```

**Điều kiện tiên quyết quan trọng nhất:** agent không thể sửa trực tiếp folder được bảo vệ bằng shell, built-in patch, MCP, editor, subprocess hoặc một đường quyền khác. Nếu chưa chứng minh được điều này ở một GUI/CLI, không được cấp `ENFORCED` cho GUI/CLI đó. Hooks chỉ hỗ trợ hướng dẫn và telemetry. Vì sandbox-exec đã bị đánh dấu deprecated, không chọn command đó như nền bảo vệ lâu dài duy nhất.

### Cách triển khai macOS được ưu tiên để nghiên cứu/chứng nhận

- **AgentFlowGuard.app (Swift)**: UI xác thực hành động của người dùng, có định danh code-signing; không dựa vào nội dung chat là bằng chứng bạn đã duyệt.
- **AgentFlowWriter helper**: helper do OS quản lý với quyền/identity được tách khỏi untrusted agents; mô hình có thể dùng `SMAppService` để đăng ký helper/daemon và XPC hoặc kênh IPC xác thực. Quyền của helper phải tối thiểu, không có API shell tùy ý. Cần code-signing và chứng nhận trên Mac thật.
- **Per-surface adapters**: gửi đề nghị/patch và hiển thị kết quả; không phát hành quyền. Cần xác minh app version/build và mọi đường file-write. Có thể cần biến thao tác viết built-in thành broker request; không được hứa GUI của hãng hỗ trợ điều này trước khi thử.
- **Repository access**: để chặn direct write của GUI cùng UID, cần OS isolation áp dụng cho tiến trình GUI, **hoặc** sở hữu/quyền repo bởi một principal riêng mà tiến trình GUI không thể ghi. Chỉ đưa trusted helper vào đường ghi. Điều này có thể ảnh hưởng khả năng người dùng sửa file thủ công và cần thiết kế đường chỉnh sửa hợp lệ. Không tự `chown`/`chmod` repository thật trong installer nếu chưa có phương án backup, rollback và sự đồng ý rõ ràng.

Apple: SMAppService https://developer.apple.com/documentation/servicemanagement/smappservice ; `sandbox-exec` deprecated https://man.freebsd.org/cgi/man.cgi?manpath=macOS+13.6.5&query=sandbox-exec&sektion=1

## 3. Cơ chế an toàn ghi file

**Trước ghi**: Task SPEC/approval thật + policy + session + issuer + TTL/revocation + resource epoch; proposed patch hash; expected file hash; exact root/path; test environment. **Trong ghi**: danh sách quyền whitelist; `dir_fd`/`O_NOFOLLOW`/`fstat`; chỉ regular file; `st_nlink==1` hoặc chính sách alias đã kiểm chứng; không chạy lệnh shell tùy ý; không sửa trong chỗ không thuộc task; không mở `O_TRUNC` trên inode gốc; không ghi metadata policy/Git như một file thường; giới hạn kích thước; protected parent namespace; atomically compare-and-apply với khóa bảo vệ. **Sau ghi**: durability/fsync khi áp dụng; change manifest; audit và verification freshness; xử lý partial/crash bằng cách reconciliation.

**Hardlink**: pre-existing alias phải bị nhận diện. Chặn alias trong *broker* không thể bảo vệ nếu shell/editor của agent còn quyền ghi qua alias; phải ngăn nguồn direct write từ OS. Hardlink tạo **sau** khi sandbox bắt đầu, pre-opened writable file descriptors và directory rename races đều phải được kiểm thử riêng. Không thể chỉ scan links tại startup.

**Dữ liệu hệ thống**: ACL, xattrs, file flags, file provider, case-folding/Unicode, APFS behavior cần chứng nhận. Scratch writer Đ2.1 từ chối xattrs không hiểu để tránh âm thầm làm mất metadata, nhưng chưa chứng minh bảo toàn ACL trên Mac. Một file trong `.git` cần giao dịch Git có quyền riêng, không sử dụng general FILE_REPLACE.

**Atomicity**: `os.replace` giúp chuyển tên file nguyên tử trong một directory có trust boundary, nhưng **không biến nhiều files + SQLite thành một transaction nguyên tử**. Reconciliation/audit record và recovery cần thiết. `flock` chỉ là khóa hợp tác, không ngăn một process có quyền filesystem bỏ qua khóa.

## 4. Dữ liệu grant — tránh tự cấp quyền

`agentflow_security.grant_protocol.SignedWriteIntentVerifier` xác minh chữ ký và kiểm tra đầy đủ repo_id, task_id, SPEC hash/revision, session, provider, path, content before/after hash, resource_id, fencing epoch, nonce, issued/expiry. Không phát hành hoặc cấp quyền. Kết quả luôn `execution_authorized=false`; private key **chỉ có trong mock test ngắn hạn trong RAM**, không có file key trong gói.

Production signer phải ở trust realm tách biệt và chỉ ký khi có human provenance thật. Kiểm tra chữ ký không đủ nếu agent có thể thay trust store hoặc phát hành own key. Cũng chưa có durable nonce ledger và service identity attestation trong nguyên mẫu này.

## 5. Quy tắc nghiệm thu không thương lượng

- G2 chỉ PASS khi cơ chế **bắt buộc** bảo vệ mọi đường ghi đã được tuyên bố cho đúng OS/build/app build, kể cả khi hooks bị tắt/hỏng.
- Trusted Approval được xác minh bằng human-controlled UI/realm; agent không thể tự ký hoặc tự nhận approve.
- Không có implicit `sudo`, không dùng quyền root rộng hoặc helper có command-execution tùy ý.
- Không thất thoát dữ liệu task khác, cả cùng file, khác file chung contract, Git index, test DB, generated artifacts.
- Unit tests và synthetic sandbox chỉ đo tính nhất quán thuật toán; không thể cấp native certification.
- Kết quả của một phiên bản ứng dụng không tự áp dụng cho bản cập nhật mới.
- Không bảo đảm thì dùng `NOT_CERTIFIED`/`READ_ONLY` thay vì hạ tiêu chuẩn.

## 6. Phần nào đã triển khai và phần nào còn thiếu

| Thành phần | Hiện trạng |
|---|---|
| D1 state/SQLite, event log, recovery | Prototype và tests đạt trong container |
| D2 receipt signature verification và replay ledger | Prototype; không có trusted human issuer |
| D2.1 signed exact write-intent verification | Prototype, không authorize |
| D2.1 hardened scratch compare-and-replace | Prototype, không áp dụng repo thật |
| D2.1 hardlink/symlink/traversal/concurrent regression | Automated tests, không có native GUI process |
| Trusted macOS Approval UI/Control Plane | Chưa xây dựng/chứng nhận |
| Protected macOS Mutation Service + OS isolation | Chưa xây dựng/chứng nhận |
| Codex & Claude GUI/CLI mandatory write coverage | Chưa chứng nhận |
| Safe task-scoped Git transaction | Chưa xây dựng/chứng nhận |
| Multiwriter proof trên Mac thật | Chưa có |

**Chưa cần người dùng chạy thêm bất cứ test nhỏ nào.** Khi các thành phần native được xây dựng và tự kiểm tra đầy đủ, sẽ xuất một bộ chứng nhận **một lượt** gồm test harness cố định, cách rollback và evidence report cho người dùng giúp kiểm thử.
