# G2.1 — Nghiên cứu bảo mật, triển khai logic và kiểm thử đối kháng

**Trạng thái cuối của G2: `BLOCKED_NATIVE_MACOS_CERTIFICATION_REQUIRED`**. Đây là bản nghiên cứu/đóng gói phát triển; **không** dùng để sửa source code sản phẩm.

## Những gì đã tự thực hiện

1. Phân tích đầu ra macOS của người dùng: 4/5 synthetic checks đáp ứng kỳ vọng, hardlink alias đã thay đổi protected canary.
2. Đọc tài liệu Apple về hardlink, symlink, secure file operations, `SMAppService`, App Sandbox, và giới hạn `sandbox-exec`; đối chiếu tài liệu của Codex/Claude về sandbox/hooks.
3. Xây mô hình kiểm soát có phân quyền độc lập (được mô tả chi tiết trong `G2_TRUST_BOUNDARY_DESIGN_V2.md`).
4. Thêm `HardenedScratchWriter`: từ chối hardlink/symlink/special file/traversal/reserved paths; kiểm tra hash, payload, epoch; khóa hợp tác; ghi file tạm với dirfd; replace rồi fsync. Chỉ giới hạn thư mục scratch độc lập.
5. Thêm `SignedWriteIntentVerifier`: chữ ký Ed25519 ràng buộc repo/task/SPEC/session/provider/path/hash/epoch/nonce/time; **không phát hành grant, không cho quyền ghi**.
6. Thêm ma trận **42 nhóm rủi ro**, ghi rõ hạng mục đã kiểm thử local, đã quan sát lỗi trên Mac, chưa kiểm chứng native hoặc mới ở mức thiết kế.
7. Viết test cho lỗi hardlink, policy path, same-file concurrent writers, signatures, malformed payload, crash / recovery ở tầng trước; chạy lại bộ kiểm thử D0/D1/D2.

## Vì sao chưa thể gọi đây là giải pháp bảo mật hoàn chỉnh?

Code chưa có nơi người dùng xác nhận bằng UI được bảo vệ, chưa có signer/key store độc lập, chưa có native macOS service tách quyền, chưa có bắt buộc chặn direct write của Codex/Claude GUI/CLI, chưa có secure Git transaction và native multiwriter proof. Các modules Python chạy cùng UID với agent **không** thể tự ngăn agent bỏ qua chúng. Do đó gói này không tự cài vào repo, không bật quyền ghi và không cho phép fake G2 PASS.

## Cách chứng nhận đúng và giảm phiền bạn

Thay vì yêu cầu người dùng chạy từng script thử nghiệm mỗi khi tìm ra một rủi ro mới, phát triển và tự kiểm tra đầy đủ trên môi trường độc lập. Sau khi có macOS protected service được build/sign, control plane được bảo vệ và các adapter có cơ chế gửi request ổn định, **mới** phát hành một gói nghiệm thu macOS duy nhất, với fixture giả, rollback, manifest, tập tình huống cố định và báo cáo tự tổng hợp. Cần thử trên bốn bề mặt khi chúng đã được cài đặt; chưa có Codex CLI thì bề mặt đó giữ NOT_CERTIFIED. Không tạo lệnh sudo hoặc chown bất ngờ.

## Release gates

| Cổng | Hiện trạng |
|---|---|
| G0 | Đã PASS từ baseline trước |
| G1 | Đã PASS từ baseline trước |
| G2 hardlink vulnerability reproduced and mitigated in broker lab | Local prototype PASS (NOT a sandbox fix) |
| G2 trusted human approval + protected signer | NOT_IMPLEMENTED |
| G2 mandatory OS write boundary, all relevant surfaces | NOT_IMPLEMENTED / NOT_CERTIFIED |
| G2 native multiwriter + crash/fd/alias proof | NOT_TESTED |
| G2 overall | BLOCKED |

## Nguồn tham khảo nhà cung cấp

- Apple Secure Coding Guide — Race Conditions & Secure File Operations: https://developer.apple.com/library/archive/documentation/Security/Conceptual/SecureCodingGuide/Articles/RaceConditions.html
- Apple `SMAppService`: https://developer.apple.com/documentation/servicemanagement/smappservice
- Apple app sandboxing: https://developer.apple.com/documentation/Security/accessing-files-from-the-macos-app-sandbox
- macOS `sandbox-exec` deprecated: https://man.freebsd.org/cgi/man.cgi?manpath=macOS+13.6.5&query=sandbox-exec&sektion=1
- OpenAI hooks: https://learn.chatgpt.com/docs/hooks
- OpenAI sandbox: https://learn.chatgpt.com/docs/sandboxing
- Anthropic Claude sandbox research: https://www.anthropic.com/research/claude-code-sandboxing
