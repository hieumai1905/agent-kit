# Một prompt khởi tạo

Mở agent tại thư mục dự án rồi gửi nguyên khối dưới đây. Agent tự clone và setup; sau đó bạn giao việc bình thường. **Thư mục làm việc hiện tại lúc nhận prompt là đích mặc định**, được chốt trước khi clone hoặc đổi thư mục.

Bản hiện hành: **v1.1.0-rc3**, bản thử để kiểm thử thực tế. Runtime pin theo tag; các tag cũ giữ nguyên. Prompt hiện hành được duy trì trên `main`.

```text
Thiết lập và áp dụng Agent Workflow Kit v1.1.0-rc3 cho thư mục làm việc
hiện tại của agent, để sau đó tôi giao việc bình thường.

Trước khi clone hoặc đổi thư mục, chạy pwd -P và ghi đường dẫn tuyệt đối
thành TARGET_CWD. Đây là đích mặc định cho --repo, AGENTS.md và CLAUDE.md.
Không suy đích từ tên chat, repo từng làm hoặc thư mục chứa kit. Đối chiếu
canonical Git root; nếu root ở cha, có nhiều repo hoặc chưa có Git, làm rõ
đích trước khi apply. Không tự nâng root, chọn repo con, git init hoặc cài hàng loạt.

Repo kit: https://github.com/hieumai1905/agent-kit.git — pin tag v1.1.0-rc3.
Resolve commit thật của tag từ remote, đối chiếu HEAD và ghi lại SHA đã dùng.
Clone bằng git clone --branch v1.1.0-rc3 --depth 1 vào
~/.local/share/agent-workflow-kit/v1.1.0-rc3 hoặc vị trí bền vững ngoài đích.
Nếu đã có clone, kiểm origin, tag/commit và thay đổi local trước khi dùng;
không reset/pull đè hoặc tự chuyển main/latest khi tag không dùng được.
Đọc release/RELEASE.json, kiểm version 1.1.0-rc3 và chạy tools/verify_release.py.
Thiếu Git/Python 3.11+/quyền/network thì báo điều kiện thiếu, không tự cài thêm.

Tôi chọn ADVISORY, duyệt contract trực tiếp trong chat, một writer. Tôi cho
phép setup đúng phạm vi: clone/runtime/state/backup ngoài project; preview
rồi làm mới managed workflow trong AGENTS.md và CLAUDE.md; giữ nguyên quy
tắc riêng; lập inventory và thêm đúng guidance kit-only chưa tracked vào
Git local exclude. Không sửa product .gitignore, hook/Husky, global config,
index/source, model/auth/settings; không untrack/unstage/skip-worktree hoặc
viết đè managed block tùy biến. Không hỏi lại các bước setup đã được ủy quyền.

Đọc BOOTSTRAP.md của đúng tag và chỉ dẫn/override đang hiệu lực. Dùng setup
--mode advisory --upgrade: review preview rồi --apply cùng --repo/state-home.
Nếu nâng cấp, giữ state-home, task/history và các thay đổi đang có; không
xóa hoặc tạo state mới thay lịch sử. Giữ protocol delegated đã chọn trước
bằng flag tương ứng; setup không tạo/gia hạn H/D. Tracked/mixed guidance
hoặc conflict phải báo BLOCKED cùng file/lý do; không bypass bằng ignore.

Đọc lại cả hai file sau cài; đối chiếu helper path, version, mode, đích,
state và việc áp dụng trong session hiện tại. Kiểm manifest/doctor,
inventory/artifacts check, baseline source/HEAD/index và backup transaction.
SETUP_LOCAL_READY chỉ là kết quả local. Chỉ báo SETUP_READY sau readback
và xác nhận session đang theo workflow; nếu chưa áp dụng được thì báo
NEEDS_SESSION_REFRESH hoặc BLOCKED, không READY giả.

Mọi artifact chỉ phục vụ kit phải local-only và ngoài working tree, trừ
hai guidance kit-only được local exclude. Theo dõi cả file sinh thêm và
kiểm INDEX trước/sau staging được duyệt riêng và trước bàn giao. Phân biệt
file sản phẩm với file vận hành kit; nội dung trùng fingerprint cần bằng
chứng nguồn gốc gắn đúng path/hash. Path kit đã biết, marker và state vẫn
phải chặn; thiếu bằng chứng thì dừng phân loại. Không stage/commit/push/deploy
hoặc sửa source trong lần setup này.

Sau setup: hỏi/khảo sát độc lập trả lời trực tiếp; việc code nhỏ dùng
contract ngắn, việc phức tạp mới phân tích sâu. Chờ tôi duyệt đúng contract,
lưu/readback quyết định và recheck trước patch, sửa đúng scope, chạy test
thực và bàn giao. Dùng work start/checkpoint/finish, resume --compact khi
cần; tự xử lý JSON/IDs và tái sử dụng binding/revision vừa đọc trong chat.
Finish đã lưu handoff thì không tạo checkpoint bàn giao lặp. Verification
có binding của lần kiểm riêng; nguồn/contract đổi phải revalidate, không
gắn PASS cũ sang nguồn mới. State là báo cáo chưa xác thực, không khôi phục
quyền từ checkpoint hoặc tự chốt giả định sản phẩm. Từ yêu cầu tiếp theo
tôi sẽ giao việc bằng ngôn ngữ bình thường.

Với nhiều repo, khai báo từng Git root và write_paths/read_paths trong
contract; work sources chụp footprint trước test, finish dùng tested_sources_file.
Không dùng hash repo chính đại diện repo khác hoặc nâng bằng chứng legacy
thiếu coverage thành CURRENT. Ưu tiên CLI trực tiếp, wrapper phải giữ mã lỗi
bằng checked client; nonzero/BLOCKED phải dừng trước patch. Output thường gọn;
chỉ đọc chi tiết khi thiếu fact thật, không chạy lại mutation để xem verbose.
Product testtree/fixtures đặt ngoài inventory kit-only. Chờ process theo
khoảng hợp lý, không đọc log không đổi hoặc lặp test khi không có lý do mới.
```
