# Một prompt khởi tạo

Mở đúng dự án trong agent coding, rồi gửi nguyên khối dưới đây. Không chạy các lệnh setup trong repo kit để thay cho dự án đích.

```text
Thiết lập Agent Workflow Kit v1.0.1 cho dự án tôi đang mở.

Repo kit: https://github.com/hieumai1905/agent-kit.git — pin tag v1.0.1.
Tôi chọn ADVISORY, duyệt contract trực tiếp trong chat, một agent ghi tuần tự.
Tôi cho phép clone kit ra ngoài dự án, khởi tạo state/backup bên ngoài và làm
mới managed workflow trong AGENTS.md, CLAUDE.md theo BOOTSTRAP.md của tag này.
Hãy tự thực hiện đầy đủ quy trình setup đó, không hỏi lại các bước đã được
ủy quyền; giữ nguyên quy tắc riêng và mọi thay đổi code/Git đang có.

Bắt buộc kiểm tra chỉ dẫn/override đang có hiệu lực, dry-run rồi nâng cấp
đúng mẫu kit, đọc lại cả hai file và xác nhận helper path, version, mode,
checkpoint/contract/test/handoff đều đúng. Không chỉ clone rồi báo xong;
không chạy /init để tạo một workflow khác. Nếu custom block hoặc override
xung đột, báo BLOCKED cùng file/lý do cụ thể, không ghi đè hay báo READY giả.

Sau setup, đọc và áp dụng workflow vừa cài cho chat này; chỉ báo SETUP_READY
khi các điều kiện trong BOOTSTRAP.md đều đạt. Không sửa source, thêm dependency,
đổi settings/quyền/model, tự bật ủy quyền H/D hoặc stage/commit/push/deploy.
Từ yêu cầu tiếp theo tôi sẽ mô tả công việc bình thường; bạn tự làm preflight,
trình contract ngắn chờ tôi duyệt, rồi checkpoint trước patch, test và bàn giao.
```
