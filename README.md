# Agent Workflow Kit v1.1.0 — bản gọn

Workflow dùng với coding agent trong thư mục dự án hiện tại: hiểu yêu cầu, giữ đúng phạm vi đã duyệt, sửa code, kiểm thử và lưu tiến độ. Agent tự nhận identity của phiên; người dùng giao việc bình thường, không quản lý task ID, hash hoặc session.

## Bắt đầu

Copy toàn bộ khối trong [INIT_PROMPT.md](INIT_PROMPT.md) và gửi vào chat của dự án muốn dùng. Prompt tự clone tag `v1.1.0` ra ngoài repo, xác minh commit/manifest, setup ADVISORY, backup/nâng cấp block kit trong `AGENTS.md` và `CLAUDE.md`, rồi đọc lại hướng dẫn để áp dụng ngay trong chat đó.

Mặc định là thư mục đang làm việc lúc bắt đầu. Setup chỉ áp dụng cho chat/dự án được chỉ định; không tự nâng cấp chat khác hoặc sửa code sản phẩm. Sau `SETUP_READY`, giao việc như bình thường. Một yêu cầu rõ ràng đã được duyệt không cần hỏi lại cùng quyền đó.

## Luồng làm việc

```text
begin → sửa code → verify → handoff
                    ↓ test lỗi
                  retry → sửa → verify
```

- Việc nhỏ dùng contract QUICK; bằng chứng CODE/CLI/UI được xác định từ yêu cầu thật trước approval. CLI không tự phát sinh gate Chrome; UI vẫn cần kiểm chứng thực tế.
- Helper trả receipt ngắn và `next_command`, tự mang các binding. Identity lấy từ provider; không truyền session ID trong luồng thường.
- Nghiên cứu trả lời trực tiếp. Nếu cần lưu context, giữ một note riêng của chat trong artifact directory. Structured brief chỉ dùng cho triển khai nhiều mốc đã duyệt.
- `work context` cho resume; `work pause` lưu tiến độ và nhả writer ở điểm an toàn. Một repo có một writer hợp tác; không tự takeover.

[Cách dùng và payload](docs/QUICKSTART.md) · [Setup/upgrade](BOOTSTRAP.md) · [Recovery và API nâng cao](docs/RECOVERY.md)

## Tệp dự án và dữ liệu kit

Runtime clone, state, backup, payload, note, log và receipt của kit ở ngoài cây repo dự án. Chỉ guidance kit-only được bảo vệ bằng local exclude; không sửa `.gitignore`/hooks để che dữ liệu. Product regression tests vẫn thuộc code dự án.

Setup giữ nguyên task/history, luật riêng ngoài managed blocks và thay đổi chưa commit. Tracked/mixed/customized guidance hoặc override xung đột phải được đối chiếu; không xóa luật, force-add, tự unstage/untrack hay reset để đi tiếp. Kit có kiểm tra artifacts và INDEX nhưng không tự stage/commit/push/deploy hoặc đổi dependency/model/settings.

## Bằng chứng và giới hạn

Bản ứng viên nền đạt 482 ca hồi quy, 25 ca được bỏ qua theo phạm vi; 17 ca JavaScript và 31 bước smoke. Chỉnh hướng dẫn cuối đã qua 44 ca liên quan và ba kiểm tra cuối về word budget/upgrade.

Ca CLI đối chứng hoàn tất trong khoảng 121 giây với bằng chứng CLI đầy đủ; bản trước chưa hoàn tất trong giới hạn 240 giây. Ca phân tích vẫn tăng usage do dùng brief API thừa; hướng dẫn cuối đã bỏ đường dùng đó, nhưng chưa đo lại bằng model. Vì vậy **chưa có kết luận giảm usage chung hay agent hiểu việc tốt hơn**. Các ca giảm lược/unit checks không thay nghiệm thu ứng dụng/UI thật.

ADVISORY và writer là cơ chế hợp tác, không phải khóa ghi hệ điều hành hoặc xác thực approval. Runtime cũ, API nâng cao và công cụ ghi tùy ý không tự tham gia writer. Passing tests không có nghĩa đã được phép publish.

## Kiểm tra gói

```sh
python3 -B /ABS/KIT/tools/verify_release.py
```

Manifest kiểm tra tính toàn vẹn của gói, không phải chữ ký nhà phát hành. Phiên bản: `v1.1.0`. [MIT License](LICENSE).
