# Đ2.2 Native macOS Trusted Control Plane — Architectural Contract / Not Implemented

**Không có signed native helper hoặc trusted UI trong RC.1. Không sử dụng tài liệu này như chứng nhận an toàn.**

## Trust boundary bắt buộc

1. Agent nằm trong một security domain không thể ghi trực tiếp vào working tree được bảo vệ.
2. UI phê duyệt có nguồn gốc người dùng đáng tin cậy, không dùng chat text, env flag hoặc agent-editable key.
3. Protected control plane có signing keys, approval ledger, policy và resource epoch ngoài quyền tác động của agent.
4. Mutation service nhận chính xác patch cho một path/version và chỉ thực thi nếu approval/session/repo/policy/resource lease còn hợp lệ.
5. Mọi đường ghi trực tiếp (`shell`, `apply_patch`, `MCP`, native GUI editor, child process, preopened FD, hardlink, rename, shared Git index) phải bị cưỡng chế hoặc bề mặt đó bị NOT_CERTIFIED.
6. OS-level process/identity isolation là điều kiện tiên quyết, không thể suy ra từ việc Python verifier PASS.

## Phương án native nên triển khai và chứng minh trên Mac

Ứng dụng macOS với UI riêng và code-signing; helper/daemon quản lý qua Apple Service Management (`SMAppService`) và kênh IPC/XPC xác thực client; permission/identity đủ tách biệt để apps agent không thể ghi trực tiếp repo hoặc trust state. Service không cấp shell tùy ý và không cho phép user-chosen path ngoài repository được đăng ký. Hạn chế quyền theo mục đích, giữ explicit backup và rollback, không tự `chmod/chown` repo thật.

`SMAppService` chỉ quản lý helper, không bảo đảm helper tự có namespace an toàn hoặc quyền filesystem tách biệt. Signed XPC protocol không giải quyết được các đường ghi trực tiếp có sẵn của app hãng thứ ba.

## Giao thức mutation cần kiểm thử

- Input: user-approved task+SPEC hash, authenticated session identity/build, repo identity, exact target path, current file hash, target content hash, fencing generation, expiry/nonce, proposed patch bytes.
- Verify: policy+grant+session/revocation, path normalization/Unicode/case, no symlink/hardlink, regular file, ACL/xattrs, ownership, resource lock, expected content and version in *same protected operation*.
- Apply: atomic temp-file replacement inside authorized directory, fsync, before/after audit, two-phase reconciliation across DB and filesystem, verify no stale writer or pre-opened FD.
- Git: separate protected index/resource transaction; no default `git add -A`; coordinate staging and commits per task.
- Refuse: policy modifications, direct writer attempts, unsupported file types or metadata, native capability not certified, failed/missing approval, outdated session, ambiguous ownership.

## Tiêu chí G2 Pass

Trên đúng Mac/app build: trusted user attestation; hooks disabled/timeouts; direct writes via all supported tools fail, including hardlink aliases and preopened FDs; protected service does not expose arbitrary command execution; two independent sessions and Git/test resources do not corrupt each other. All failures report NOT_CERTIFIED. G2 không thể được tự chốt trong Linux container hiện tại.

## Tài liệu tham khảo

- Apple SMAppService: https://developer.apple.com/documentation/servicemanagement/smappservice
- Apple Secure Coding Race Conditions: https://developer.apple.com/library/archive/documentation/Security/Conceptual/SecureCodingGuide/Articles/RaceConditions.html
- Codex sandbox: https://learn.chatgpt.com/docs/sandboxing
- Claude Code sandbox: https://www.anthropic.com/research/claude-code-sandboxing
