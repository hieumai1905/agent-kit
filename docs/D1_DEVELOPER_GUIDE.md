# Hướng dẫn phát triển và kiểm tra Đ1 (không phải setup guide cuối)

**Yêu cầu:** Python 3.10+ với sqlite3/stdlib, Git chỉ cần cho kiểm thử installer Đ0. Chưa yêu cầu API key, model hoặc Codex/Claude trên máy.

Trong folder `Agent_Workflow_System_V3_Dev_D1`:

```bash
PYTHONPATH=. python3 tools/audit_wave1.py --output .release/WAVE1_ACCEPTANCE.json
```

Trên macOS, thử coordinator với **repository tạm, không phải repo công việc**:

```bash
mkdir -p /tmp/agentflow-d1-demo/repo /tmp/agentflow-d1-demo/state
PYTHONPATH=. python3 -m agentflow_core.cli \
  --repo /tmp/agentflow-d1-demo/repo \
  --state-home /tmp/agentflow-d1-demo/state init

PYTHONPATH=. python3 -m agentflow_core.cli \
  --repo /tmp/agentflow-d1-demo/repo \
  --state-home /tmp/agentflow-d1-demo/state new-task \
  --title 'Test D1' --request 'Kiểm thử lưu trạng thái task ở vùng ngoài repo'

PYTHONPATH=. python3 -m agentflow_core.cli \
  --repo /tmp/agentflow-d1-demo/repo \
  --state-home /tmp/agentflow-d1-demo/state doctor

PYTHONPATH=. python3 -m agentflow_core.cli \
  --repo /tmp/agentflow-d1-demo/repo \
  --state-home /tmp/agentflow-d1-demo/state backup
```

Khi không truyền `--state-home`, mặc định là vùng user-local `~/Library/Application Support/AgentWorkflowV3/repositories/<repo-id>/` **ngoài Git working tree**. Các file chứa task text có thể nhạy cảm; thư mục được giới hạn quyền filesystem cho owner, nhưng chưa cách ly khỏi process cùng user.

`restore-new`: chỉ chấp nhận thư mục state home **chưa có** repository state, không ghi đè data đang hoạt động. Kiểm tra checksum/identity trước khi khôi phục; để chuyển sang dùng state đã khôi phục phải cấu hình root state theo quy trình quản trị (chưa tự động trong Đ1).

**D1 không cài hooks, không cập nhật AGENTS.md/CLAUDE.md, không đổi config app, không sửa project source.** Bản `source-preview/` chỉ dùng cho hồi quy, không phải installer chính thức.

## Khắc phục lỗi thường gặp

| Lỗi | Giải thích / xử lý |
|---|---|
| `State database is not initialized` | Chưa chạy `init`. `doctor` chỉ đọc và báo trạng thái. |
| `outside repository working tree` | Đường state home đang nằm bên trong repo; chọn vị trí ngoài repo. |
| `ConflictError` | Revision hoặc idempotency không còn hợp lệ; đọc lại trạng thái và gửi lại đúng operation. |
| `GateNotImplemented` | Đ1 cố tình chặn phê duyệt/ghi code vì chưa có trusted execution của Đ2. |
| `Unversioned/Preview database detected` | Không thể nhập SQLite Preview trực tiếp; cần migration tool riêng có audit. |
| `Recovery destination already exists` | Không overwrite; chọn một state home mới. |
| `Migration history mismatch` | DB/migration không đúng checksum; ngừng cập nhật và kiểm tra backup. |

**Không được tự “khắc phục” các lỗi này bằng cách sửa trực tiếp SQLite hoặc tắt trigger/guards.**
