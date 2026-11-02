# Agent Workflow Kit

Quy trình làm việc với coding agent ngay trong dự án: **yêu cầu → contract → duyệt → checkpoint → triển khai → kiểm thử → bàn giao**.

[MIT License](LICENSE) · Python 3.11+ · Git · Bản hiện hành: **v1.0.2**

## Bắt đầu bằng một prompt

Mở **dự án cần làm việc** trong coding agent, sau đó gửi nguyên [prompt khởi tạo](INIT_PROMPT.md). Agent tự clone phiên bản đã pin ra ngoài dự án, chạy setup và kiểm tra kết quả theo [BOOTSTRAP.md](BOOTSTRAP.md). Bạn không cần nhập Task ID hoặc tự chạy lệnh cài.

**Đích mặc định là thư mục làm việc hiện tại của agent lúc nhận prompt.** Agent chốt `pwd -P` trước khi clone/đổi thư mục và dùng đúng đường dẫn đó cho setup. Nếu Git root ở thư mục cha hoặc có nhiều repo đích chưa rõ, agent hỏi lại trước khi apply; không tự chọn repo khác. Prompt dùng chung cho các dự án, không chứa tên Concat/Teammate hay đường dẫn máy cụ thể.

Lấy prompt hiện hành từ [INIT_PROMPT.md trên main](https://github.com/hieumai1905/agent-kit/blob/main/INIT_PROMPT.md). Prompt pin runtime ở tag `v1.0.2`; các tag và ZIP đã phát hành không bị sửa khi cập nhật hướng dẫn trên `main`.

Setup bắt buộc:

1. Kiểm tra project, Git, runtime và các chỉ dẫn/override đang có hiệu lực.
2. Clone tag `v1.0.2` vào vị trí bền vững bên ngoài project; kiểm manifest và version.
3. Dry-run rồi **làm mới cả AGENTS.md và CLAUDE.md** bằng installer của kit, giữ nguyên các quy tắc riêng ngoài managed block.
4. Đọc lại hai file, xác nhận helper path/mode/state/override và workflow đang áp dụng trước khi báo **SETUP_READY**.

Không chạy `/init` để sinh workflow riêng thay kit. Nếu block bị tùy biến hoặc override xung đột, setup phải báo **BLOCKED** cùng nguyên nhân; không ghi đè hoặc báo thành công giả. Prompt đã cho phép setup đúng phạm vi nên không cần duyệt lại từng lệnh cài thông thường.

## Yêu cầu

- Python **3.11+** và Git có sẵn.
- Agent có thể đọc file, chạy terminal và clone GitHub theo quyền hiện có.
- Một agent ghi tuần tự. Codex local là môi trường đã có bằng chứng sử dụng; chưa khẳng định mọi provider/model đều đã được nghiệm thu.
- Clone, state và backup đặt ngoài working tree của dự án. Setup không tự cài package, đổi auth/model hoặc cấu hình sandbox.

Installer mặc định STRICT. Prompt init chủ động chọn **ADVISORY, duyệt trực tiếp trong chat**. Cài đặt không phê duyệt task code hoặc tự cấp ủy quyền H/D.

## Dùng hằng ngày

Sau SETUP_READY, gửi yêu cầu bình thường:

> Sửa lỗi [mô tả], kết quả mong muốn là [kết quả]. Giữ nguyên [ràng buộc]. Không commit/push/deploy.

Agent khảo sát phần liên quan và trình contract ngắn. Khi đồng ý, trả lời **Duyệt contract này**. Agent lưu checkpoint quyết định trước patch, kiểm thử theo phạm vi và báo kết quả thật.

Khi tiếp tục ở chat khác:

> Tiếp tục việc [tên việc]. Đọc checkpoint và đối chiếu Git/contract/quyết định hiện tại trước khi làm.

Nếu có nhiều task gần giống nhau, agent cần hỏi chọn đúng việc. State/checkpoint là dữ liệu bàn giao chưa xác thực; không tự khôi phục quyền ghi hay delegation đã kết thúc.

## Kiểm tra cài đặt

Các lệnh dưới đây dành cho agent, chạy từ kit; `/ABS/PROJECT` là project đã xác định:

```sh
python3 -B tools/verify_release.py
python3 -B tools/agentflow.py --repo /ABS/PROJECT version
python3 -B tools/agentflow.py --repo /ABS/PROJECT doctor
python3 -B tools/practical_smoke.py
```

`practical_smoke.py` kiểm luồng task/contract/checkpoint/handoff và cài/gỡ/rollback trên repo tạm; không chạy model hoặc sửa project thật. Nó sinh báo cáo local được Git ignore. Exit 0 của một diagnostic không tự là approval; agent phải đọc nội dung JSON.

## Tài liệu

| Tài liệu | Nội dung |
|---|---|
| [INIT_PROMPT.md](INIT_PROMPT.md) | Một prompt copy/paste để khởi tạo |
| [BOOTSTRAP.md](BOOTSTRAP.md) | Các bước setup và điều kiện SETUP_READY |
| [Sử dụng](docs/USAGE.md) | Giao việc, resume, cập nhật, gỡ và rollback |
| [Quy trình agent](docs/AGENT_WORKFLOW.md) | Contract, giới hạn scope, thực thi, test/review, status |
| [Continuity](docs/CONTINUITY.md) | Checkpoint theo mốc và tiếp quản công việc |
| [Ủy quyền tùy chọn](docs/DELEGATED_ADVISORY.md) | Protocol H/D khi người dùng chọn riêng |
| [Guard trước patch](docs/CHECKED_PATCH_FLOW.md) | Luồng checkedPatchFlow của delegated ADVISORY |

## Nội dung bản dùng

```text
agentflow_core/       State, task, contract và backup
agentflow_runtime/    Workflow, installer, checkpoint và handoff
agentflow_security/   Dependency kiểm tra quyền/chẩn đoán của runtime
agentflow_si/         Helper chẩn đoán và preflight của CLI
docs/                Tài liệu vận hành hiện hành
tools/               CLI, kiểm manifest, smoke và checked patch flow
release/             Metadata phiên bản và manifest
LICENSE
```

Repo hiện hành chỉ giữ phần phục vụ cài đặt/vận hành và dependency cần thiết. Không phân phối preview installer, security mutation labs, roadmap, báo cáo/PDF lịch sử, dữ liệu pilot hay bộ test phát triển. Các phiên bản cũ vẫn thuộc lịch sử Git; dùng tag hiện hành và shallow clone trong prompt init để lấy bản gọn.

ZIP và checksum của bản dùng có tại [Releases](https://github.com/hieumai1905/agent-kit/releases). Mã kiểm thử phát triển và hồ sơ nghiệm thu được lưu riêng khỏi gói người dùng.

## Giới hạn

ADVISORY là quy ước làm việc dựa trên sự tuân thủ của agent và permissions provider. Kit chưa có trusted approval adapter, khóa ghi OS, thu hồi nguyên tử hoặc bảo đảm nhiều writer. Helper/report không tự cấp quyền, chứng thực PASS hoặc thay quyết định người dùng. Không tự stage/commit/push/deploy hay mở rộng yêu cầu.

## License

Mã nguồn và tài liệu trong bản hiện hành được phát hành theo [MIT License](LICENSE). Copyright © 2026 hieumai1905.
