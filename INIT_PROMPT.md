# Một prompt khởi tạo

Mở terminal của agent tại thư mục dự án cần dùng, rồi gửi nguyên khối dưới đây. Prompt dùng chung cho các dự án; không cần thay tên hoặc điền đường dẫn. **Thư mục làm việc hiện tại lúc nhận prompt là đích mặc định**, được chốt trước khi clone hoặc đổi thư mục.

Prompt hiện hành được duy trì trên `main`; runtime được pin ở tag `v1.0.2`. Các tag và ZIP đã phát hành giữ nguyên.

```text
Thiết lập và áp dụng Agent Workflow Kit v1.0.2 cho thư mục làm việc
hiện tại của agent, để sau đó tôi chỉ cần giao việc bình thường.

Trước khi clone hoặc đổi thư mục, chạy pwd -P (hoặc tương đương) và ghi
lại đường dẫn tuyệt đối thành TARGET_CWD. Đây là đích setup mặc định:
dùng cùng đường dẫn đó cho --repo và vị trí AGENTS.md, CLAUDE.md.
Không suy đích từ tên chat, repo từng làm hoặc thư mục clone kit.
Đối chiếu Git root tại TARGET_CWD. Nếu Git root là thư mục cha, hoặc có
nhiều repo đích còn mơ hồ, hỏi tôi chốt phạm vi trước khi apply; không tự
nâng lên thư mục cha, chọn repo con hay cài hàng loạt. Nếu TARGET_CWD
chưa thuộc Git repo, giữ nguyên đích và không tự chạy git init.

Repo kit: https://github.com/hieumai1905/agent-kit.git — pin tag v1.0.2.
Commit phải khớp: d2083cf2d2901e966f2397c85c6c6d907cb6dbfb.
Tự clone bằng git clone --branch v1.0.2 --depth 1 vào
~/.local/share/agent-workflow-kit/v1.0.2 hoặc vị trí bền vững ngoài đích.
Nếu đã có clone, kiểm origin/tag/commit và thay đổi local trước khi dùng;
không reset/pull đè nội dung hoặc tự chuyển sang main/latest.

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
khi các điều kiện trong BOOTSTRAP.md đều đạt, kèm TARGET_CWD và project path
thực tế để tôi đối chiếu. Nếu session chưa áp dụng được, báo
NEEDS_SESSION_REFRESH hoặc BLOCKED. Không sửa source, thêm dependency,
đổi settings/quyền/model, tự bật ủy quyền H/D hoặc stage/commit/push/deploy.
Từ yêu cầu tiếp theo tôi sẽ mô tả công việc bình thường; bạn tự làm preflight,
trình contract ngắn chờ tôi duyệt, rồi checkpoint trước patch, test và bàn giao.
```
