# Dynamic Model Advisor — ĐỀ XUẤT, chưa tự đổi model

## Đã chốt

- Người dùng chọn nền tảng (Codex/Claude). Không tự động nhảy nền tảng khi hết usage.
- Mỗi nền tảng có các model/mức suy luận khác nhau; model thấp có thể không hỗ trợ subagent. Workflow core không dùng subagent.
- Hệ thống **đề xuất** mức năng lực, không tự đổi model của phiên chính.
- Model và usage thay đổi theo thời gian; không được hardcode tên phiên bản cố định hoặc giả vờ biết hạn mức còn lại.

## Cơ chế đang có trong kit

`model-advice T-... --provider codex|claude` đọc `contract.json` risk/complexity, `model-policy.json` usage_mode theo từng provider và lists (allowed + known_available), trả `FAST/BALANCED/DEEP` cùng những model candidate có thật trong cả hai danh sách. Nếu chưa cấu hình => trả tier và `[]`, không gợi ý tên model bịa ra.

`providers.codex.usage_mode` / `providers.claude.usage_mode`: UNKNOWN / NORMAL / LOW / CRITICAL. `UNKNOWN` nghĩa là không có dữ liệu, không đồng nghĩa usage dồi dào. `LOW/CRITICAL` chỉ dùng để tiết kiệm cho task rủi ro thấp/vừa. High-risk vẫn cần năng lực cao hoặc hoãn/escalate.

## Tích hợp cấu hình trong repo

File `.agentflow/policies/model-policy.json` lưu model được **người dùng cho phép** cho từng nền tảng. Để cấu hình chính xác, xem `/model` ở CLI/app, xác minh model thực sự truy cập được, sau đó cập nhật danh sách. Hiện tại kit chưa tự đọc account-level usage Claude/Codex; đây là khoảng trống được ghi rõ thay vì suy diễn.

Không tự dùng model mới ngay khi xuất hiện. Quy trình đề xuất: model được phát hiện → trạng thái CANDIDATE → kiểm thử task nhỏ đại diện → người dùng cho phép → thêm vào danh sách ưu tiên. Khi đổi model, nên checkpoint trước nếu context có thể thay đổi.

## Escalation theo bằng chứng

- Đơn giản & xác định → FAST/BALANCED; khi rủi ro cao → DEEP.
- Khi 2 vòng xử lý thất bại mà không có tiến bộ → phân tích nguyên nhân lại, cân nhắc DEEP.
- Nếu task mới liên quan security/payment/concurrency, tự đề xuất review mạnh.
- Không tự ép model thấp xử lý vấn đề chưa giải được; ghi blocker và đề xuất đổi model.

## Việc cần chốt trong phiên sau

1. Các model thực sự có trong tài khoản Codex và Claude hiện nay.
2. Danh sách allow/deny riêng cho từng nền tảng.
3. Chính sách ưu tiên: chất lượng tối đa, cân bằng, hay bảo toàn usage.
4. Khi usage còn ít, xử lý task high risk thế nào (hoãn, hỏi, tiếp tục chuẩn bị)?
5. Nguồn usage công khai/chính thức có thể đọc được từ CLI/app mà không lách giới hạn dịch vụ.
6. Cách đánh giá model mới trên bộ task benchmark đại diện repo.
