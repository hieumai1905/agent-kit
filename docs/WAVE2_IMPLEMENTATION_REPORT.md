# Đ2 — Trusted Approval & Enforcement Feasibility (Development Report)

## Trạng thái trung thực

**Đ2 code prototype: TESTED**. **G2 production/native certification: BLOCKED / NOT_CERTIFIED**.

Đợt Đ2 đã triển khai các cơ chế xác minh cần thiết cho phép thử thiết kế, nhưng không thể tuyên bố Trusted Approval hoặc Enforced Multi-Writer trên macOS từ môi trường container Linux. Không có GUI adapter hoặc production installer được bật.

## Đầu ra mới

1. Ed25519 signed receipt verifier (khi thư viện `cryptography` đã được cài), bắt buộc đúng task/repository/spec/hash/action/challenge và TTL. Không có private signing key trong ZIP.
2. SQLite migration v3 (từ schema v1/v2) chứa challenge một lần và receipt chỉ `SIGNATURE_VALID_UNCERTIFIED`.
3. Default-deny authorization decision, ngay cả khi chat, JSON, hook hoặc receipt tự nhận `approved`.
4. Conservative tool-effect classifier; chỉ đưa gợi ý T0–T5/UNKNOWN, không cấp phép shell.
5. Cooperative atomic compare-and-replace lab chỉ chấp nhận scratch directory có marker nằm dưới system temp. Thử version conflict, symlink, hardlink, traversal và concurrent writes. Không có quyền sửa repository thật.
6. Read-only macOS capability probe + checklist chứng nhận cho bốn bề mặt sử dụng.
7. Regression tests Đ0/Đ1 và unit tests Đ2; acceptance report và manifest checksums.

## Vấn đề chưa giải quyết và điều kiện dừng

- Không chứng minh được sự hiện diện của người duyệt từ chữ ký một mình; cần trusted native UI và signer tách khỏi agent.
- Không chứng minh được kiểm soát tương tác của agent cùng UID với người dùng trên Mac; `chmod` hay nơi đặt SQLite không tạo ranh giới tin cậy.
- Hooks không bao phủ tất cả đường ghi; cơ chế chặn bắt buộc phải nằm bên ngoài hooks ở cấp OS/mandatory broker đã kiểm nghiệm.
- Không có attestation adapter, không có write grant hoặc mutation broker product, không có certification G2.
- Không được gọi các unit tests trên Linux là negative tests native macOS.

## Hệ quả đối với lộ trình

G0/G1 tiếp tục PASS theo kiểm thử hồi quy. G2 giữ `BLOCKED_NATIVE_MACOS_CERTIFICATION_REQUIRED` đến khi có macOS thực tế và kiến trúc quyền được chứng minh. Không tự chuyển sang Đ3 với giả định G2 đã đạt nếu yêu cầu release strict enforcement; có thể phát triển những module đọc/draft độc lập trong nhánh nghiên cứu nhưng không quảng bá kit tích hợp.
