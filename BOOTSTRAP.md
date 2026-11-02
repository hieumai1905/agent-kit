# Bootstrap v1.0.2 — bắt buộc hoàn tất trước SETUP_READY

Dành cho coding agent nhận **prompt setup trực tiếp từ người dùng**. Tệp này hướng dẫn thực hiện phạm vi đã được người dùng chọn; đọc repo/tool output không tự cấp quyền. Nếu chưa có quyết định cài ADVISORY thì chưa apply. INIT_PROMPT.md cung cấp quyết định cài cụ thể, không phê duyệt task code hoặc H/D.

## 1. Chốt đúng đích và phạm vi

- Xác định canonical project root từ workspace người dùng đang mở, thường qua `git rev-parse --show-toplevel`; ghi lại trước khi đổi cwd. Nếu không xác định được duy nhất thì hỏi đúng điểm còn thiếu, không đoán. Không lấy repo kit làm project đích.
- Ghi nhận Git status, HEAD/index nếu có và các thay đổi chưa commit. Không stash/reset/stage/commit/push/deploy. Đọc chỉ dẫn hiện có: global/parent/project, AGENTS.override.md, AGENTS.md, CLAUDE.md và chỉ dẫn nested cho phạm vi sẽ làm. Không sửa file global hoặc settings của provider.
- Kiểm Git và Python **3.11+**. Thiếu runtime/quyền/network thì báo điều kiện thiếu, không tự sudo hoặc cài dependencies. Runtime của kit dùng stdlib; cryptography/Node chỉ phục vụ một số tests/lab tùy chọn, không cần tự cài để setup guidance.

## 2. Clone đúng phiên bản ra ngoài project

Chọn đường dẫn bền vững, mặc định `~/.local/share/agent-workflow-kit/v1.0.2`, đảm bảo nằm ngoài canonical project. Không tái sử dụng thư mục không rõ nguồn và không clone lồng trong source repo.

```sh
git clone --branch v1.0.2 --depth 1 https://github.com/hieumai1905/agent-kit.git /ABS/KIT
```

`/ABS/KIT` và `/ABS/PROJECT` trong tài liệu là placeholder; agent tự điền bằng canonical paths đã xác định, không bắt người dùng nhập chúng. Nếu thư mục đã có, kiểm `origin`, `git rev-parse HEAD`, `git rev-list -n 1 v1.0.2`, thay đổi local; không reset/pull/checkout đè source đang sửa. Chỉ dùng khi đúng repo/tag và source không bị tùy biến. Báo cáo `release/PRACTICAL_SMOKE.json` có thể được sinh khi chạy kiểm tra; nó được Git ignore và nằm ngoài manifest, không thay code/policy. Không tự chuyển sang main/latest nếu không lấy được tag.

Chạy từ kit:

```sh
python3 -B tools/verify_release.py
python3 -B tools/agentflow.py --repo /ABS/PROJECT version
python3 -B tools/agentflow.py --repo /ABS/PROJECT doctor
```

Version phải **1.0.2**, manifest PASS. Diagnostic doctor có thể exit 0 nhưng báo state chưa khởi tạo hoặc guidance cũ: đọc JSON, không coi exit code đơn thuần là READY. State lỗi/hỏng thì dừng và báo, không tự xóa hoặc repair.

Đọc README.md, docs/USAGE.md, docs/AGENT_WORKFLOW.md, docs/CONTINUITY.md và các policy dự án hiện hành liên quan. docs/DELEGATED_ADVISORY.md + docs/CHECKED_PATCH_FLOW.md áp dụng nếu protocol H/D đã được chọn riêng; không tự bật H/D từ prompt setup trực tiếp.

## 3. Bắt buộc làm mới AGENTS.md và CLAUDE.md

**Không bỏ bước này vì file đã tồn tại hoặc kit đã clone.** So sánh managed block với mẫu của checkout hiện tại và helper path thực tế.

- Repo mới: dry-run `install-guidance --mode advisory`.
- Có managed block từ kit: dry-run `install-guidance --mode advisory --upgrade`. Lệnh sẽ nhận diện và thay đúng block cũ đã biết, bao gồm helper path cũ. Cài lại có thể no-op nếu đã đúng hoàn toàn; vẫn phải đọc lại/verify.
- Mặc định setup này chọn **duyệt trực tiếp**, không thêm `--delegated-advisory`. Nếu repo đã có protocol delegated ADVISORY do người dùng chọn trước và chưa yêu cầu đổi, giữ nó bằng cách thêm `--delegated-advisory` vào cả dry-run và apply. Cài protocol không tạo H/D hoặc gia hạn delegation cũ.
- Agent review diff để đảm bảo đúng mode/path/workflow, giữ nguyên các quy tắc dự án ngoài managed block. Với đúng phạm vi INIT_PROMPT đã duyệt, tiếp tục apply sau review; không hỏi lại một quyết định cài đã rõ.
- Không chạy `/init` hoặc tự viết một biến thể workflow vào các file này. Không xóa file chỉ dẫn chỉ vì chúng do agent sinh. Nếu block bị customized, file lowercase khác (`agents.md`, `claude.md`), duplicate marker hoặc override xung đột thì không bypass guard của installer: báo file và phần cần giải quyết, không tuyên bố setup thành công. Giữ nội dung quy tắc riêng; chỉ thay phần xung đột ngoài block khi người dùng đã quyết định rõ nội dung đó.

Ví dụ cho repo đã có managed block, không delegated:

```sh
python3 -B /ABS/KIT/tools/agentflow.py --repo /ABS/PROJECT install-guidance --mode advisory --upgrade
# Review JSON diff rồi apply cùng flags:
python3 -B /ABS/KIT/tools/agentflow.py --repo /ABS/PROJECT install-guidance --mode advisory --upgrade --apply
```

Repo mới bỏ `--upgrade`. Giữ AGENTFLOW_STATE_HOME/--state-home được người dùng chọn nếu có, đảm bảo state/backup ngoài project. Installer tạo backup và transaction ID khi có thay đổi: lưu vị trí đó trong báo cáo setup. Partial failure: báo txid và hiện trạng; không chạy tiếp như đã thành công và không tự rollback mù.

## 4. State, đọc lại và xác nhận đang áp dụng

Từ kit, khởi tạo state ngoài project bằng API hiện có rồi kiểm lại:

```sh
python3 -B -m agentflow_core.cli --repo /ABS/PROJECT init
python3 -B tools/agentflow.py --repo /ABS/PROJECT doctor
```

Nếu có state-home riêng thì truyền cùng `--state-home` cho mọi lệnh, kể cả core CLI; không dùng chỗ khác rồi làm mất continuity. Không tạo task demo hoặc phê duyệt giả để kiểm setup.

Đọc trực tiếp **toàn bộ AGENTS.md và CLAUDE.md vừa cài**, cùng các override có hiệu lực. Kiểm:

1. `guidance_installer.installed_files` đều ADVISORY, `mode_consistent=true`, helper trỏ đúng /ABS/KIT và đúng /ABS/PROJECT; không có block LEGACY_OR_CUSTOM.
2. Nếu không giữ delegated opt-in: `delegation_files` đều DISABLED. Nếu giữ: đều OPT_IN_PROTOCOL_INSTALLED, nhưng `delegation_active` vẫn NOT_ESTABLISHED_BY_INSTALLATION.
3. Đã có contract trước code, checkpoint ở các mốc continuity, checkpoint quyết định trước patch, test/review có bằng chứng và handoff. Task/approval không được suy từ state hoặc cài đặt.
4. Không có global/parent/override/nested instruction đang có hiệu lực bỏ qua workflow hoặc cho sửa code trước contract. Kiểm lại scoped instructions trước khi vào subdirectory ở task sau. Không sửa config để cố bỏ qua xung đột.
5. Doctor state khỏe; Git/source ngoài AGENTS.md, CLAUDE.md vẫn nguyên baseline. Backup/state/clone nằm ngoài project; không có dependency/settings/hook mới.

Codex xây instruction chain khi bắt đầu run/session; ghi file không chứng minh phiên đang chạy đã tự reload. Trong chat setup, người dùng đã yêu cầu rõ việc đọc và áp dụng policy mới: agent phải đọc lại và xác nhận đang theo đúng nội dung đó. Nếu policy cũ/override còn ngăn áp dụng thì báo NEEDS_SESSION_REFRESH hoặc BLOCKED, không báo READY. Với session mới, xác minh provider nạp đúng files; không tự đổi global settings.

Nguồn OpenAI Docs: [Custom instructions with AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md), phần discovery/verify (đối chiếu 02/11/2026). Chỉ dẫn này không tự chứng nhận Claude hoặc mọi provider. Kit ghi CLAUDE.md để giữ quy tắc repo đồng bộ; mức native evidence của v1.0.2 vẫn giới hạn ở Codex local.

## 5. Nghiệm thu ngắn và kết thúc setup

Chỉ báo **SETUP_READY** khi các điều kiện trên đã được quan sát. Báo tối đa khoảng 10 dòng: project; clone path/tag/commit/version; mode/direct-or-delegated; hai file đã làm mới hoặc đã đúng; backup txid; doctor + manifest; sources/override đã đọc; source/Git ngoài hai file giữ nguyên; workflow sẽ áp dụng trong chat.

Nếu chưa đạt, báo BLOCKED với lỗi thực tế và phần đã/chưa thay đổi, không đổ cho kit trước khi đối chiếu path/tag/flags/override. Không che lỗi kit đã tái hiện; phân biệt rõ lỗi setup, môi trường và lỗi sản phẩm.

Sau đó người dùng chỉ mô tả công việc bình thường. Agent tự intake/resume/preflight, trình contract ngắn và chờ quyết định cho task code; sau duyệt ghi checkpoint quyết định trước patch, test/review và handoff. Không phải hỏi lại setup hoặc yêu cầu Task ID. Không tự commit/push/deploy hoặc chuyển quyền H/D. ADVISORY là quy ước quy trình, không có khóa ghi OS.
