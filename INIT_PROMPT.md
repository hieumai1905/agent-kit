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

Toàn bộ artifact chỉ phục vụ kit phải là local-only, không nằm trong commit
của dự án. Đặt clone, state/DB, backup, contract/checkpoint của kit, log,
báo cáo, inventory và file tạm ngoài working tree. Phân biệt chúng với
contract/docs/tests của sản phẩm: không ignore nhầm dữ liệu cần commit.
Tôi cho phép thêm đúng đường dẫn file kit-only chưa tracked vào Git local
exclude, lấy vị trí bằng git rev-parse --git-path info/exclude; ví dụ
/AGENTS.md, /CLAUDE.md ở root. Giữ nguyên các rule có trước, không dùng glob
rộng, không sửa .gitignore của sản phẩm, global config hoặc hook/Husky.
Nếu file đã tracked, chứa quy tắc sản phẩm hoặc artifact kit đã staged,
không coi ignore là bảo vệ, không tự untrack/unstage/skip-worktree; báo
BLOCKED để chốt cách xử lý. Lưu inventory artifact ngoài repo và lưu quy
tắc local-only này ngoài managed block của AGENTS.md/CLAUDE.md để phiên
sau đọc được; không thay mẫu workflow bên trong block của kit.
Trước mọi stage/commit được tôi duyệt riêng, đối chiếu inventory, phạm vi
task và nội dung INDEX thực tế; kiểm lại sau staging. Nếu có artifact kit
hoặc managed block lọt vào index, kể cả do force-add/đổi tên, dừng trước
commit và báo rõ. Không tự dùng git add -f hoặc stage hàng loạt.

Bắt buộc kiểm tra chỉ dẫn/override đang có hiệu lực, dry-run rồi nâng cấp
đúng mẫu kit, đọc lại cả hai file và xác nhận helper path, version, mode,
checkpoint/contract/test/handoff đều đúng. Không chỉ clone rồi báo xong;
không chạy /init để tạo một workflow khác. Nếu custom block hoặc override
xung đột, báo BLOCKED cùng file/lý do cụ thể, không ghi đè hay báo READY giả.

Sau setup, đọc và áp dụng workflow vừa cài cho chat này; chỉ báo SETUP_READY
khi các điều kiện trong BOOTSTRAP.md và kiểm local-only ở trên đều đạt,
kèm TARGET_CWD, project path, inventory/exclude và staged check thực tế.
Nếu session chưa áp dụng được, báo
NEEDS_SESSION_REFRESH hoặc BLOCKED. Không sửa source, thêm dependency,
đổi settings/quyền/model, tự bật ủy quyền H/D hoặc stage/commit/push/deploy.
Từ yêu cầu tiếp theo tôi sẽ mô tả công việc bình thường; bạn tự làm preflight,
trình contract ngắn chờ tôi duyệt, rồi checkpoint trước patch, test và bàn giao.
```
