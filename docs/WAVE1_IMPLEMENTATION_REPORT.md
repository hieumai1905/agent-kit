# Báo cáo thực thi và nghiệm thu G1 — Canonical Foundation

**Ngày:** 2026-10-29 · **Đợt:** Đ1/Đ7 · **Loại:** Development release chưa được chứng nhận trên macOS GUI.

## 1. Mục tiêu so với kết quả

| Đầu việc Đ1 | Hiện trạng trong mã | Bằng chứng/giới hạn |
|---|---|---|
| State runtime bên ngoài working tree | Đã triển khai | `StateStore` dùng SHA-256 canonical repo path dưới `~/Library/Application Support/AgentWorkflowV3`; test không làm thay đổi product file |
| Canonical Task/Contract | Đã có nền | `tasks`, immutable `contract_revisions`, optimistic `revision`, idempotency; DoR semantic thuộc Đ3 |
| Approval references | Chỉ có `UNVERIFIED` | D1 không thể xác minh phê duyệt con người; mọi chuyển tới APPROVED bị chặn |
| Session state | Đã có nền | Sessions/provider/lifecycle và optimistic CAS; trust identity/fencing thuộc Đ2 |
| Work item và dependencies | Đã có nền | Cơ chế tạo work item, guard dependency cycle, bảo vệ trạng thái EXECUTING/COMPLETED chưa được chứng nhận |
| Policy versioning | Đề xuất có version/hash | `PROPOSED` chưa được phép active; người dùng duyệt policy ở Đ2/Đ4 |
| Evidence references | Đã có nền | `reported_status` + `attestation=UNVERIFIED`, artifact revision/dependency, freshness; verified test attestation thuộc Đ5 |
| Resource intent | Đã có metadata | Deny intent conflict, generation/fencing metadata; **không cấp quyền ghi** |
| SQLite migrations | Đã triển khai | v1→v2 atomic, no implicit commit from `executescript`, checksum history, reject Preview/unversioned DB |
| Audit | Đã có cơ chế integrity | Append-only triggers, SHA-256 chain, không bảo vệ chống adversary cùng quyền user |
| Consistency concurrent | Đã kiểm thử | BEGIN IMMEDIATE, optimistic version, idempotency, nhiều process update cùng row |
| Backup/recovery | Đã triển khai | SQLite backup consistent, verify checksum/foreign keys/audit, restore **chỉ vào vùng mới**; không ghi đè state đang chạy |
| Doctor CLI | Đã triển khai | Schema, foreign keys, audit, repo identity, gắn nhãn `enforced:false` |

## 2. Kết quả kiểm thử

**Nguồn chính xác:** `.release/WAVE1_ACCEPTANCE.json`, tạo bằng `PYTHONPATH=. python3 tools/audit_wave1.py --output .release/WAVE1_ACCEPTANCE.json`.

- **G0:** kiểm thử Preview kế thừa + installer Đ0.
- **G1:** migration, race conditions, no self-approval, failed transactions, hard process exit mid-transaction, metadata không vào repo, policy/evidence freshness và recovery.
- **G2–G7:** `NOT_RUN`. Không giả định adapter capability hoặc strict enforcement từ kết quả test Python.

Các trường hợp xuất hiện trong G1: migration idempotent, migration history tampered fail-closed, nguồn Preview unversioned reject, task revision conflict, simultaneous initialize/update, contract immutability, resource intent expiry không takeover, rollback sau crash, audit tampering signal, fresh restore và backup sai repo/checksum.

## 3. Giới hạn phải xử lý ở Đ2–Đ7

**Đ2:** Nguồn phê duyệt con người đáng tin cậy; policy administration tách quyền; sandbox/write broker thực sự; session identity và capability certificates theo bản macOS/app. SQLite bên ngoài repo và file mode 0600 **không đủ** chống agent dùng cùng UID.

**Đ3:** Task Navigator, natural-language intent, RIG, DoR, proposal/approval protocol. API Đ1 hiện dành cho dev/test, chưa đáp ứng UX dùng bằng chat.

**Đ4:** Technical Plans, Work Graph semantic và Engineering Profile đã duyệt theo stack/domain. D1 có work-item/dependency primitives, chưa có Scheduler.

**Đ5:** Trusted atomic mutation, verified test evidence, change manifests, Git transactions, code review, DoD evidence. D1 `resource_intents`/`evidence` chỉ là metadata chứ không có quyền ghi hay sự chứng nhận PASS.

**Đ6:** Final completion, handoff packet, Model Advisor/usage, metrics.

**Đ7:** Installer và tài liệu hướng dẫn cài/sử dụng đã được kiểm nghiệm trên bốn bề mặt, release manifest và E2E.

## 4. Điều kiện chuyển Đ1 → Đ2

Chỉ chuyển tiếp với trạng thái G1 PASS khi mọi bài test đã chạy PASS và mã nguồn tương ứng được khóa checksum trong `.release/WAVE1_ACCEPTANCE.json`. G2 tiếp tục với **read-only feasibility spike trên repo thử**, không cấp quyền ghi cho adapter nào trước khi xác nhận được trust boundary.
