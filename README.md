# Agent Workflow Kit

Workflow cho coding agent trong dự án hiện tại: **hiểu yêu cầu → contract → duyệt → checkpoint → sửa → kiểm chứng → bàn giao**.

[MIT License](LICENSE) · Python 3.11+ · Git · **v1.1.0-rc4 — bản thử để kiểm thử thực tế**

## Bắt đầu

Mở agent tại dự án rồi gửi prompt trong [INIT_PROMPT.md](INIT_PROMPT.md). Agent tự clone tag `v1.1.0-rc4` ra ngoài dự án, kiểm đúng bản và setup tại thư mục đang làm việc ban đầu. Nếu nâng cấp, giữ nguyên state/history và mọi thay đổi đang có.

Có thể [tải ZIP của tag](https://github.com/hieumai1905/agent-kit/archive/refs/tags/v1.1.0-rc4.zip), giải nén ngoài dự án rồi làm theo [BOOTSTRAP.md](BOOTSTRAP.md).

```sh
python3 -B /ABS/KIT/tools/verify_release.py
python3 -B /ABS/KIT/tools/agentflow.py --repo /ABS/PROJECT setup --mode advisory --upgrade
python3 -B /ABS/KIT/tools/agentflow.py --repo /ABS/PROJECT setup --mode advisory --upgrade --apply
```

Setup preview trước apply, làm mới AGENTS.md/CLAUDE.md, giữ nội dung riêng, backup ngoài project, lập inventory và dùng Git local exclude hẹp. File tracked/mixed, managed block tùy biến, override chưa giải quyết hoặc artifact trong index phải BLOCKED. Agent đọc lại chỉ dẫn đang hiệu lực và kiểm kết quả trước SETUP_READY. Setup local không chứng minh provider đã nạp hướng dẫn.

## Giao việc bình thường

> Sửa lỗi [triệu chứng], kết quả mong muốn [kết quả]. Giữ nguyên [ràng buộc]. Không commit/push/deploy.

Agent khảo sát và trình contract ngắn cho việc nhỏ; việc phức tạp mới cần phân tích sâu. Khi đồng ý, trả lời **Duyệt contract này**. Agent ghi quyết định trước patch, kiểm điều kiện, sửa, chạy kiểm tra sát phạm vi và bàn giao bằng chứng.

Hỏi/đọc/nghiên cứu độc lập được trả lời trực tiếp. Agent phân biệt yêu cầu đã xác nhận, facts từ code và phương án đề xuất, không hỏi lại điều đã rõ hoặc tự chốt chính sách sản phẩm.

Lượt chỉ khảo sát/đề xuất/contract chưa triển khai giữ trong chat, không mặc định chạy helper. Sau khi duyệt triển khai, agent lưu đúng contract và quyết định, readback/recheck trước patch. Tracking bền vững hoặc handoff của việc đang làm vẫn dùng state.

## Thao tác nội bộ của agent

| Thao tác | Vai trò |
|---|---|
| `work start` | Tìm việc đang có / tạo contract và checkpoint chờ quyết định |
| `work checkpoint` | Lưu milestone với CAS/binding; quyết định tự readback/recheck, `--check` dùng sau gián đoạn |
| `work finish` | Đánh giá báo cáo theo acceptance/preserve, kiểm artifact và lưu bàn giao |
| `work sources` | Chụp toàn bộ footprint nhiều repo trước test, không thực thi test |
| `resume TOPIC --compact` | Đọc tóm tắt có giới hạn; đối chiếu freshness, không khôi phục quyền |
| `work history` | Tra lịch sử theo trang, không xóa bằng chứng cũ |
| `artifacts check` | Kiểm index blobs, artifact roots và file chưa tracked |

Người dùng không nhập IDs/JSON. Payload mẫu nằm trong [USAGE.md](docs/USAGE.md). CLI cũ và state v1.0.2 được giữ tương thích. H/D, SI, model-advice là đường nâng cao riêng; không tự bật.

Rc4 sửa finish với payload thực tế, bổ sung cách kiểm giả định và hành trình sử dụng trước khi chọn thiết kế. Thay đổi tương tác được nghiệm thu riêng với unit/mock; thiếu kiểm tra thao tác thực phải báo thiếu. File triển khai được refine trong policy đã duyệt, giữ nguyên contract/approval; exact file list vẫn là mặc định. Các cơ chế nguồn nhiều repo, CAS, local-only và bằng chứng chưa xác thực được giữ. Chưa khẳng định cải thiện quyết định/usage tổng quát; kết quả fixture có giới hạn cần được đối chiếu với công việc thật.

## Kiểm chứng và giới hạn

`VERIFIED_REPORTED` nghĩa là báo cáo agent đủ các mục yêu cầu, không phải trusted verification. Thiếu reproduction, execution hoặc coverage làm giảm mức kết luận. Resume giữ verification từ bản ghi lịch sử gốc, có freshness contract/source riêng; checkpoint tiến độ không làm mới bằng chứng cũ. Helper không chạy command trong JSON, không tự approve/complete hoặc phát hành. Quyền và quyết định thực vẫn do user/provider.

Artifact vận hành kit ở ngoài product tree; chỉ guidance kit-only chưa tracked được giữ ở root bằng local exclude. Checker đọc INDEX, phát hiện marker/fingerprint/SQLite state kể cả đổi tên; đọc thêm các runtime roots đã đăng ký. Nội dung trùng fingerprint cần đối chiếu nguồn gốc; có thể ghi báo cáo sản phẩm gắn path/hash qua artifacts classify-product. Path kit đã biết/marker/state vẫn chặn. File chưa biết nguồn hoặc bản sao đã biến đổi cần agent review. Không ignore rộng docs/tests/contracts; không tự untrack/unstage, sửa .gitignore/hook/global config. Không có cơ chế chặn tuyệt đối commit ngoài workflow. Kiểm tra bị giới hạn hoặc không đọc được phải báo BLOCKED.

Một writer tuần tự; snapshot/CAS không là khóa OS hay sandbox. Codex local là môi trường thử; không khẳng định mọi provider/model đã được nghiệm thu. Không thêm API/MCP/dependencies/model calls vào runtime.

## Kiểm tra và phục hồi

```sh
python3 -B /ABS/KIT/tools/verify_release.py
python3 -B /ABS/KIT/tools/practical_smoke.py
```

Smoke chạy trên fixture tạm; không gọi model, không sửa dự án thật và không thay thế benchmark agent. Test phát triển, trace và báo cáo nghiệm thu nằm ngoài gói người dùng. Cách nâng cấp/gỡ/rollback: [USAGE.md](docs/USAGE.md). Gỡ guidance không xóa lịch sử state; rollback từ chối đè file người dùng đã sửa sau cài.

## Tài liệu

- [Setup và READY](BOOTSTRAP.md)
- [Workflow](docs/AGENT_WORKFLOW.md)
- [Cách dùng và payload](docs/USAGE.md)
- [Debug và verification](docs/VERIFICATION.md)
- [Continuity](docs/CONTINUITY.md)
- [Delegated protocol tùy chọn](docs/DELEGATED_ADVISORY.md)

Runtime và hướng dẫn thuộc [MIT License](LICENSE). Copyright © 2026 hieumai1905.
