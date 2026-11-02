# D1 Canonical State — thiết kế API và giới hạn

## 1. Các đối tượng chính

| Đối tượng | Chủ sở hữu logic theo thiết kế | D1 triển khai |
|---|---|---|
| Task | RIG/task registry | `tasks`, scope per repository, lifecycle/CAS |
| Contract | RIG | Immutable `contract_revisions`, canonical JSON SHA-256 |
| Approval | Trusted Approval service (Đ2) | Chỉ `approval_references.UNVERIFIED` |
| Session | Session coordinator | Lifecycle/heartbeat metadata; chưa có identity verification |
| Work item | EEW-03 | Item records và dependency DAG guard |
| Engineering/Domain policy | Policy Admin + EEW-04/05 | Immutable proposals; không có API activate |
| Artifact/Evidence | EEW-07 | Artifact versioning, evidence dependencies; chưa verified |
| Resource intent | Resource Coordinator | Intent generation, conflict deny; không phải write lease |
| Audit/operations | Local State Coordinator | Append-only events + idempotency ledger |

## 2. Bất biến có trong mã

- `APPROVED ≠ AUTHORIZED`: D1 không thể tự tạo approval hay authorization.
- `reported PASS ≠ VERIFIED`: `evidence.attestation` chỉ có `UNVERIFIED`.
- Thay đổi cùng row phải gửi `expected_revision`; stale updates bị từ chối.
- Retry cùng `request_key` + payload trả cùng kết quả; khác payload báo conflict.
- Contract revisions không bị sửa hay xóa qua API; revision tạo mới, hợp đồng cũ còn nguyên.
- Resource intents dùng generation; expired intent KHÔNG tự trở thành tài nguyên free.
- Work dependency phải cùng task; tránh self/cycle.
- Trạng thái không thể nhảy đến `APPROVED`, `EXECUTING`, `WORK_ITEM_COMPLETED` qua API Đ1.
- Backup khôi phục vào một state home mới; không overwrite DB/working tree đang chạy.

## 3. Triển khai SQLite

`schema.py`: phiên bản schema hiện tại là `2`. Migration `1` tạo repositories, tasks, contracts, sessions, approval references, audit, operations. Migration `2` bổ sung work items, policies, artifacts, evidence, resource intents.

`migrate()` giữ `BEGIN IMMEDIATE` trước khi đọc version; dùng từng câu lệnh `execute()` để tránh implicit commit của `executescript()`. Kiểm tra checksum các migration trước khi nâng cấp. Nếu gặp DB Preview chưa được version hóa, **từ chối nhập tự động**.

SQLite dùng WAL, `foreign_keys=ON`, `synchronous=FULL`, `busy_timeout`; mọi sự kiện ghi có idempotency key, audit và thay đổi dữ liệu được commit trong cùng transaction. Đây là **tính nhất quán ứng dụng**, không phải bảo vệ quyền OS.

## 4. Python API (mã tham khảo)

```python
from agentflow_core import LocalCoordinator

app = LocalCoordinator('/absolute/path/to/test/repo', '/tmp/agentflow-state-test')
task = app.create_task('Ví dụ', 'Thêm bộ lọc trạng thái cho màn hình sản phẩm',
                       request_key='client-request-unique-123')
started = app.transition_task(task['task_id'], task['revision'], 'PREFLIGHT')
revision = app.revise_contract(task['task_id'], started['revision'], {
    'objective': 'Cho phép chọn và lọc sản phẩm theo trạng thái',
    'acceptance': ['Trả đúng sản phẩm theo bộ lọc']
})
proposed = app.transition_task(task['task_id'], revision['revision'], 'WAITING_APPROVAL')
# Không có lệnh approve/write-authorize trong D1.
```

D1 CLI có các lệnh tạo/đọc hồ sơ phục vụ kiểm thử, **không** được yêu cầu người dùng thông thường nhập Task ID hoặc tự chỉ định scope. Giao diện tự nhiên là nhiệm vụ Đ3.

## 5. Giới hạn security

- Hash contract và chain audit không được ký/chứng thực bằng khóa ở một miền quyền độc lập.
- Local SQLite có thể bị sửa bởi process chạy cùng UID. D2 phải thiết kế Trusted Control Plane và prove enforcement.
- Repo path canonicalization chỉ dành cho định danh repo và tách state; chưa phải path-constrained write broker chống symlink/TOCTOU.
- Idempotency, leases, policy proposals và evidence đều là **metadata**, không phải năng lực thực thi sản phẩm.
