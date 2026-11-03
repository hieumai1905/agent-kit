# Một prompt khởi tạo

Mở agent tại thư mục dự án và gửi nguyên khối dưới đây. Sau setup, giao việc bằng ngôn ngữ bình thường. Đích mặc định là **thư mục đang làm việc khi nhận prompt**, được chốt trước clone/cd. Đây là bản thử, chưa có kết luận giảm tổng usage hoặc nghiệm thu UI thật. Prompt không tự cập nhật các chat khác.

Runtime tag: **v1.1.0-slim-candidate.2**. Resolve commit của tag từ remote và đối chiếu HEAD trước khi dùng; không fallback main/latest. Bản prompt trên main pin thêm SHA cụ thể sau khi tạo runtime commit.

```text
Thiết lập và áp dụng Agent Workflow Kit v1.1.0-slim-candidate.2 cho thư mục
làm việc hiện tại của agent; sau đó tôi sẽ giao việc bình thường.

Trước clone/cd, chạy pwd -P và chốt TARGET_CWD tuyệt đối. Đó là đích cho
--repo, AGENTS.md và CLAUDE.md. Đối chiếu canonical Git root; root ở cha,
nhiều repo hoặc chưa có Git thì làm rõ trước apply. Không tự nâng root,
chọn repo con, git init, setup hàng loạt hoặc dùng repo kit làm đích.
Không liên hệ hoặc cập nhật các chat khác.

Repo kit: https://github.com/hieumai1905/agent-kit.git
Tag bắt buộc: v1.1.0-slim-candidate.2.
Resolve commit thật của tag từ remote, đối chiếu HEAD và ghi SHA đã dùng.
Clone git clone --branch v1.1.0-slim-candidate.2 --depth 1 vào
~/.local/share/agent-workflow-kit/v1.1.0-slim-candidate.2 hoặc vị trí bền vững
ngoài mọi product tree. Clone đã có phải kiểm origin, commit, manifest và
local changes; không reset/pull đè, ghi đè clone cũ hoặc fallback main/latest.
Đọc release/RELEASE.json, kiểm version 1.1.0-slim-candidate.2 rồi chạy
tools/verify_release.py. Cần Git/Python 3.11+; thiếu điều kiện thì báo,
không tự cài dependency hoặc đổi auth/model/settings.

Tôi chọn ADVISORY, một writer, duyệt contract trực tiếp trong chat. Tôi
ủy quyền setup: clone/runtime/state/backup ở ngoài project; preview rồi
làm mới managed workflow trong AGENTS.md/CLAUDE.md; giữ mọi luật riêng và
tạo backup; inventory ngoài repo và local exclude hẹp cho đúng hai guidance
kit-only chưa tracked. Đọc chỉ dẫn/override đang hiệu lực trước apply.
Tracked/mixed guidance, block tùy biến hoặc conflict phải BLOCKED cùng lý do;
không untrack/unstage/skip-worktree, sửa ignore/hooks hoặc đè luật riêng.
Không sửa product source/.gitignore, global config, index hay settings.
Không hỏi lại các bước setup đã được ủy quyền; setup không duyệt task code.

Đọc BOOTSTRAP.md của đúng bản. Nếu nâng cấp, giữ state-home, task/history,
clone cũ và thay đổi đang có; không tạo state mới thay lịch sử. Với chat đang
có việc, setup tại điểm dừng an toàn, giữ test/process/output và checkpoint
khi cần; không cài giữa đợt patch hoặc tự hủy test. Giữ delegated protocol
đã chọn bằng flag tương ứng; setup không tạo hoặc gia hạn H/D.

Dùng đúng TARGET_CWD/state-home: preview setup --mode advisory --upgrade,
review rồi --apply cùng tham số. Đọc lại AGENTS.md/CLAUDE.md, đối chiếu helper
path, đích, version, mode, state, luật riêng và backup. Kiểm doctor, inventory,
artifacts check và bảo toàn source/HEAD/index. Chỉ báo SETUP_READY sau
readback và xác nhận session đang theo workflow. SETUP_LOCAL_READY riêng lẻ
chưa đủ; chưa áp dụng được thì NEEDS_SESSION_REFRESH hoặc BLOCKED.

Mọi file vận hành kit và file sinh thêm như receipt/log/payload/report phải
ngoài product tree, dùng artifact_directory/registered roots hẹp. Chỉ hai
guidance kit-only chưa tracked được local exclude tại root. Không đưa
runtime/state vào commit sản phẩm; kiểm INDEX trước/sau staging được duyệt
riêng. Product regression tests thuộc code sản phẩm. Không force-add,
auto-unstage/untrack hoặc ignore rộng docs/tests/contracts để che lỗi.

Sau setup, áp dụng managed AGENTS.md trong session. Hỏi/khảo sát/đề xuất trả
lời trực tiếp, chưa tạo records triển khai. Với việc code, đọc code/dữ liệu
thật, phân biệt facts/yêu cầu/giả định; trình contract ngắn gồm outcome,
scope, một ví dụ phải sửa, một ví dụ phải giữ và checks. Với tương tác, trace
input → thao tác → dependency/chờ → kết quả, gồm save/reopen khi cần.
Không tự chốt yêu cầu chưa xác nhận. Duyệt một lần cho đúng scope.

Luồng thường một batch/single Git root: sau USER duyệt dùng work begin lưu,
readback/recheck quyết định trước patch; inspect và dừng trên BLOCKED/nonzero.
Helper tự mang IDs/revisions/hashes; dùng receipt mới nhất. Sửa đúng scope,
giữ thay đổi có sẵn; work verify chạy checks đã khai báo và bind tested
sources; work handoff lưu kết quả/bàn giao. Đọc docs/SLIM.md hoặc COMMAND
--help khi thiếu options, không đọc source helper để đoán payload. Không
ghi approval/hành vi khác contract đã trình.

Fail/missing/timeout hoặc source đổi không được thành PASS. Review symptom
và preservation; không gắn hash mới cho test cũ. Phân biệt code checked,
actual workflow exercised và app ready; unit/mock không chứng minh UI thật.
Handoff thành công không tạo checkpoint/report trùng; không lặp full tests
hoặc log không đổi khi chưa có lý do mới.

Nhiều repo, refinement/batch tiếp, migration, security/permissions, billing,
delegation hoặc handoff dài dùng API nâng cao trong docs/USAGE.md; khai báo
đủ roots/write_paths/read_paths, giữ binding/CAS. Số file không tự quyết
định rủi ro. Resume bằng topic --compact; chỉ đọc thêm khi thiếu fact hay có
ambiguity thật. Không đoán task, khôi phục quyền từ state hoặc chuyển
approval/PASS sang binding mới. Scope đổi cần duyệt lại.

Kit là advisory, không cấp OS permission hoặc xác thực identity; giữ giới
hạn provider. Không tự cài dependency, đổi model/settings, thêm agents hoặc
stage/commit/push/deploy. Xong setup, báo ngắn kết quả và chờ việc tiếp theo.
```
