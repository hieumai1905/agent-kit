# Agent Workflow Kit v1.1.1

Bộ workflow gọn cho coding agent: hiểu việc, dùng đúng quyền đã giao, triển khai, kiểm thử và bàn giao bằng kết quả sử dụng. Người dùng giao việc bình thường; agent tự xử lý contract, receipt và session.

## Bắt đầu

Copy khối trong [INIT_PROMPT.md](INIT_PROMPT.md), gửi agent tại Git root dự án muốn làm việc. Prompt clone tag `v1.1.1` ra ngoài repo, xác minh commit/manifest, setup ADVISORY, backup và nâng cấp managed block của `AGENTS.md`/`CLAUDE.md`, rồi đọc lại để áp dụng trong chính chat đó.

Cần Git và Python 3.11+ có sẵn. Setup giữ state/history, luật riêng và thay đổi chưa commit. Không tự nâng cấp chat khác. Sau `SETUP_READY`, giao việc như thường lệ, ví dụ: “Sửa lỗi nút Lưu, kiểm thử và báo kết quả; chưa deploy.”

## Agent làm việc và xin duyệt thế nào?

| Tình huống | Cách xử lý |
|---|---|
| Giao triển khai rõ, quyền đã đủ | Nêu cách làm ngắn rồi thực hiện, không xin lại cùng quyền. |
| Yêu cầu đề xuất trước/chưa sửa | Khảo sát, giải thích phương án và chờ quyết định. |
| Thiếu lựa chọn sản phẩm | Kiểm tra thông tin có sẵn rồi hỏi đúng điều còn thiếu. |
| Sửa/test/bổ sung file trong allowance đã giao | Cập nhật kế hoạch kỹ thuật trước patch, tiếp tục cùng quyết định. |
| File bị khóa, thay mục tiêu hoặc tác động vượt quyền | Trình phần quyết định mới và chờ trước khi tác động. |
| Có đề xuất đang chờ | Giữ active scope/decision; chỉ tiếp tục phần độc lập đã được phép. |
| State/source/writer xung đột | Đối chiếu trước; không xin duyệt bỏ guard hoặc tự takeover. |

Tin xin duyệt giải thích vấn đề và ảnh hưởng, bằng chứng, cách sửa và lý do, đánh đổi chính, kiểm chứng và quyền cần bổ sung. Link/ID/JSON là chi tiết xem thêm. [Ranh giới và ví dụ](docs/DECISIONS.md).

## Luồng gọn

```text
begin → patch → verify → handoff
                 ↓ test lỗi
               retry → sửa → verify
```

- Bằng chứng CODE/CLI/UI theo yêu cầu thực. Unit/mock không chứng minh UI hoạt động.
- File đã biết được ghi nhận ngay từ begin. File phát sinh trong allowance dùng `work refine` trước sửa; contract và quyết định gốc giữ nguyên, PASS cũ không được mang sang footprint mới.
- `propose-contract` lưu draft riêng. `work accept-proposal` chỉ kích hoạt sau quyết định USER thực; không tự gia hạn quyền hoặc chuyển approval cũ sang contract mới.
- `work context` cho tiếp tục; writer của chính chat được đánh dấu rõ để dùng receipt hiện tại. `work pause` lưu điểm dừng và nhả writer an toàn.
- Nghiên cứu trả lời trực tiếp; khi cần lưu context chỉ giữ một note riêng ngoài repo. Structured brief dùng khi thật sự cần nhiều mốc.

[Cách dùng](docs/QUICKSTART.md) · [Setup/upgrade](BOOTSTRAP.md) · [Recovery/API nâng cao](docs/RECOVERY.md)

## Giữ repo dự án sạch

Clone, state, backup, payload, note, log và receipt của kit nằm ngoài repo dự án. Guidance kit-only dùng Git local exclude hẹp. Không sửa `.gitignore`/hooks để che dữ liệu; regression tests của sản phẩm vẫn thuộc code sản phẩm.

Tracked/mixed/customized guidance hoặc override xung đột phải được đối chiếu. Không tự xóa luật, force-add, unstage/untrack hay reset để đi tiếp. Setup kiểm artifacts/INDEX và giữ source/index/HEAD. Stage/commit/push/deploy, dependencies, model/settings và agent phụ phải nằm trong quyền USER cụ thể.

## Kiểm chứng và giới hạn

Đợt phát hành kiểm tra 529 ca hồi quy: 525 đạt, 4 ca được bỏ qua vì cần công cụ phát triển không có trong gói runtime; 38 ca liên quan sau chốt cuối đều đạt. Có 17 nhánh JavaScript, 33 bước smoke và nâng cấp thực từ rc3/v1.1.0 giữ lịch sử, source/index/HEAD; guidance trộn luật sản phẩm vẫn chặn.

Agent thật chạy 18 lượt cho 12 tình huống trên repo tổng hợp cô lập. Lần kiểm tra liên quan cuối đạt tiêu chí quyền/phạm vi/giao tiếp của từng tình huống: không hỏi lại việc đã giao, giữ read-only/khóa file, phân biệt writer của mình, giữ proposal chờ, đọc đúng bản đã duyệt, bổ sung regression trước patch và xử lý từ chối. Các lượt đầu lộ lỗi được giữ trong hồ sơ thử nghiệm; một lượt thiếu reproduction được runtime báo PARTIAL, rồi ca này được chạy lại đầy đủ. Ca đổi Page chỉ nghiệm thu cách khảo sát/trình phương án; giải pháp kỹ thuật vẫn chưa được triển khai hay kiểm UI.

Đây là ca CLI tổng hợp, không phải kiểm thử trên các chat/repo đang chạy hoặc UI approval của Codex. Không có đối chứng lặp để chứng minh giảm usage chung, độ ổn định thống kê hoặc agent luôn hiểu đúng yêu cầu. Gói Git không chứa log/state/transcript thử nghiệm.

ADVISORY, approval source và writer là cơ chế hợp tác; không xác thực người duyệt hoặc khóa ghi hệ điều hành. Runtime cũ, API thấp và công cụ ghi tùy ý không tự tham gia writer. Lệnh lỗi phải được đối chiếu; passing tests không cấp quyền publish. Lifecycle canonical có thể còn WAITING_APPROVAL sau quyết định ADVISORY; phải xem nguồn quyền USER thực và checkpoint tương ứng, không suy ra cần hỏi lại từ trường đó.

## Kiểm tra gói và license

```sh
python3 -B /ABS/KIT/tools/verify_release.py
```

Manifest kiểm tra toàn vẹn, không phải chữ ký nhà phát hành. Chỉ runtime và hướng dẫn sử dụng được phân phối; dữ liệu thử nghiệm/state không đi kèm. [MIT License](LICENSE).
