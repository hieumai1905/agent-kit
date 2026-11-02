# KẾT QUẢ NGHIÊN CỨU VÀ TỰ NGHIỆM THU — Đ2.1

**Ngày:** 29/10/2026  
**Trạng thái:** LOCAL ASSURANCE TESTS PASS; G2 SECURITY CERTIFICATION BLOCKED.

## Dữ liệu đầu vào từ người dùng trên macOS

- Darwin 25.6.0 / arm64.
- ChatGPT/Codex Desktop, Claude Desktop và Claude Code CLI đã được phát hiện. Codex CLI chưa tìm thấy.
- Synthetic Seatbelt lab v0.1 cho phép ghi trong repo và chặn direct/symlink/traversal ra ngoài.
- Synthetic lab v0.1 **KHÔNG chặn được hardlink**: canary ở khu vực ngoài repo đã đổi khi ghi thông qua alias trong repo.

## Phân tích nguyên nhân

Hardlink được tạo trước khi tiến trình vào sandbox. Alias nằm trong vùng được phép nhưng chia sẻ inode với đường dẫn protected. Quyền dựa trên đường dẫn không bảo đảm content tại inode sẽ bất biến. Ngay cả khi broker kiểm tra `st_nlink`, một agent còn quyền ghi trực tiếp vẫn có thể tránh broker. Do đó cần mandatory OS boundary và repo parent namespace có quyền được bảo vệ.

## Thiết kế và mã đã triển khai

- `agentflow_security.hardened_lab`: file safety prototype trên scratch fixture; content hash, fd-relative no-follow, nlink, regular-file check, mode, xattr fail-closed, reserved names, atomic rename, fsync, lock hợp tác, không sửa product files.
- `agentflow_security.grant_protocol`: Ed25519 signature-only verifier; claims ràng buộc repo/task/SPEC/session/provider/file/baseline/result hash/epoch/nonce/time; không bao giờ cấp quyền.
- `docs/G2_TRUST_BOUNDARY_DESIGN_V2.md`: kiến trúc protected macOS approval + mandatory mutation service; identity separation, rollback, crash/recovery và policy.
- `docs/G2_ADVERSARIAL_COVERAGE.json`: 42 nhóm rủi ro đã phân loại theo bằng chứng.
- `tools/g2_assurance_audit.py`: kiểm tra một lượt toàn bộ regression từ Đ0 đến Đ2.1; kết quả JSON riêng, luôn giữ G2 NOT_CERTIFIED.

## Bằng chứng kiểm thử tự động

Theo `.release/G2_1_LOCAL_ASSURANCE.json`:

| Suite | Số bài | Kết quả |
|---|---:|---|
| Đ0–Đ2.1 local tests, gồm 63+ bài mới và 109 bài cũ | 172 | PASS |
| Preview tests | 5 | PASS |
| **Tổng** | **177** | **PASS** |

Ghi chú: các bài test trong Python/Linux container chỉ chứng minh tính đúng đắn trong phạm vi fixture và protocol; không chứng minh OS privileges hoặc UI của Codex/Claude trên Mac.

## Phân biệt khả năng

- **Đã chứng minh tại local**: signed-intent binding, malformed input fail-closed, hardlink alias có thể ghi cùng inode, scratch writer từ chối alias, stale baseline, symlink/traversal, một trong hai writer cùng baseline thắng với cooperative lock, tests hồi quy D0–D2.
- **Chưa chứng minh**: session/approval provenance gắn với một thao tác người dùng thực sự, Keychain/SMAppService/XPC/privileged helper, OS-native mandatory deny của GUI, safety sau khi provider cập nhật, hardlink creation sau khi sandbox entry, preopened FD, parent rename race, root-owned repo/identity tradeoffs, multiwriter + Git/index isolation.

## Cổng nghiêm ngặt

`G2=BLOCKED_NATIVE_MACOS_CERTIFICATION_REQUIRED`, `enforced_execution=false`, `ready_for_user_native_certification_batch=false`. Không được tự sửa các trường này dựa trên local tests hoặc model nhận định.

**Không yêu cầu người dùng chạy thêm script ở thời điểm này.** Đợt native acceptance cuối được chuẩn bị thành một gói cố định, không phải liên tục yêu cầu chạy từng case. Nó chỉ có ý nghĩa sau khi control plane và write service thực sự được build, sign và kiểm thử trước.
