# Phạm vi chốt Agent Workflow Kit v1.0

Ngày 02/11/2026, Asia/Ho_Chi_Minh. Người dùng đã duyệt kế hoạch ba bước trong chat điều phối: chốt phạm vi → hoàn thiện bản giao → kiểm thử gói và bàn giao. Không sửa Concat, không stage/commit/push/deploy, không mở rộng chức năng.

## Phạm vi sử dụng v1.0

- Bộ kit quy trình thực dụng, phiên bản phân phối **1.0.0**; engine/guidance V3 và schema state hiện có giữ nguyên.
- Môi trường đã có bằng chứng thực tế: **Codex Desktop trên máy Mac hiện tại, một executor ghi tuần tự trên Concat**; Codex CLI đã kiểm tiếp nhận công việc ở chế độ chỉ đọc. Không suy sang mọi task hoặc provider.
- Dùng coding theo **ADVISORY** đã được chọn rõ: yêu cầu → contract được duyệt → checkpoint quyết định → patch trong phạm vi → test/review → handoff. Delegated H/D là opt-in có giới hạn; không tái sử dụng delegation đã kết thúc.
- Giữ nguyên STRICT mặc định và mọi tool/quyền provider. STRICT chỉ dẫn đọc/draft, không là khóa ghi OS do kit cung cấp.
- Giữ installer/backup/upgrade/rollback/remove, state ngoài repo, natural resume và guard đã kiểm thử. Không đổi schema, dependencies, model/provider, auth hoặc permissions.

## Không thuộc v1.0 đã chốt

OS enforcement/trusted approval broker; chống sửa cùng UID; thu hồi nguyên tử; nhiều writer đồng thời; chứng nhận Claude hoặc mọi provider; tự commit/push/deploy; đo hay cam kết mức tiết kiệm token/thời gian. G2/G5 vẫn BLOCKED với mục tiêu security certification cũ. Phát hành thực dụng này không có nghĩa đạt FINAL/ENFORCED của kiến trúc lịch sử.

## Ba bước nghiệm thu

1. Scope và giới hạn thống nhất với quyết định người dùng; không thêm chức năng.
2. Version/README/handoff/hướng dẫn dùng và báo cáo hiện hành nhất quán; lịch sử được đánh dấu, ZIP mới không ghi đè ZIP cũ.
3. Regression hiện có + smoke đạt, skip được báo riêng; giải nén/manifest/version và cài/rollback/gỡ trên repo tạm đạt; Concat cùng archive cũ nguyên hash.

Sau bàn giao: **đóng băng phát triển mở rộng**. Chỉ nhận sửa lỗi cản trở sử dụng thực tế khi người dùng giao; không tự kích hoạt backlog trong tài liệu lịch sử.
