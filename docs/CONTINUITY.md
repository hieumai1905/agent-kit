# Checkpoint và tiếp tục

State ngoài repo là báo cáo UNVERIFIED, không cấp quyền hay xác thực quyết định. Không migrate/xóa state cũ chỉ để dùng giao diện mới.

Quyền thực theo DECISIONS.md: yêu cầu triển khai rõ có thể đủ quyền; chỉ xin phần còn thiếu và giữ giới hạn trình kế hoạch trước. Đề xuất đang chờ nằm riêng, không thay active scope/decision. Context/resume hiển thị pending_proposal để phân biệt phần còn được làm và phần chưa được duyệt; agent phải tự kiểm tính độc lập, không suy từ việc có draft.

## Mốc lưu

| Mốc | Nội dung |
|---|---|
| HANDOFF/WAITING_DECISION | Khi có yêu cầu tracking bền vững hoặc handoff của việc đã có; work start tự lưu khi được dùng |
| CONTRACT_DECISION | Quyết định thực được agent quan sát, binding và source baseline; lưu/readback/recheck tự động trong một lệnh trước patch |
| SCOPE_CHANGE | Phạm vi/contract mới và phần cần quyết định lại |
| IMPLEMENTATION_VERIFICATION | Source kiểm thử, checks, kết quả và nội dung bàn giao; work finish lưu cùng một checkpoint |
| HANDOFF | Dừng giữa chừng: hoàn thành, còn lại, blockers và next action |

Chỉ lưu ở mốc thay đổi có ý nghĩa, không mỗi message hoặc câu hỏi độc lập. Agent dùng work checkpoint, expected_revision từ phản hồi trước/resume và contract_sha256 đã đọc. Xung đột thì reread/reconcile, không tự thay revision để ghi đè. Quyết định/provenance được mang tiếp nhưng không tự trở thành approval của contract khác. Save có readback; lỗi phải báo chưa lưu.

Luồng direct ADVISORY thông thường: lượt chỉ khảo sát/đề xuất/contract ở trong chat, không mặc định lập state. Sau khi được duyệt triển khai, serialize đúng phạm vi đã trình bằng start, lưu/readback/recheck quyết định trước patch. Không thêm policy hoặc nghĩa mới khi serialize. Việc đang triển khai dừng/resume vẫn phải checkpoint. Protocol delegated được chọn riêng giữ yêu cầu binding/chấp thuận riêng của nó; quy tắc nhẹ cho lượt phân tích không tạo hoặc gia hạn H/D.

## Resume

`resume "Chủ đề" --compact` chỉ đọc, trả tóm tắt giới hạn, binding, freshness, reported verification và Git snapshot. Khi thông tin bị rút gọn, đọc bản đầy đủ trước khi tác động. `work history "Chủ đề" --limit 5 --before REV` đọc lịch sử theo trang; không xóa quyết định cũ hoặc tải toàn bộ history vào context mỗi lần.

Vague/multiple matches cần chọn tên việc, không lấy task mới nhất. Missing checkpoint/state phải nói thiếu, không tạo task hoặc bịa tiến độ. Source/hash/Git/contract đổi cần đối chiếu. Saved decision không phục hồi quyền current-provider hoặc delegation hết hạn.

Legacy checkpoint-template/checkpoint-milestone/checkpoint/handoff vẫn được giữ. Payload mẫu và quy tắc local-only nằm trong USAGE.md; checkpoint legacy không tự được nâng thành dữ liệu xác thực.
