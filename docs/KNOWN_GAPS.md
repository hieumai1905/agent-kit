# Gaps đã quan sát trong source Preview — Đ0

**Nguồn:** `source-preview/Agent_Workflow_System_V3`; chỉ đọc, không cài vào repo người dùng. Những kết luận này dựa trên source/config thực tế, không phải phỏng đoán khả năng GUI.

| ID | Quan sát thực tế | Hậu quả / đợt xử lý |
|---|---|---|
| GAP-01 | `agentflow.py` tạo `docs/agentflow/tasks/*` trong working tree trong preflight | Đổi runtime/draft state mặc định ra ngoài repo — Đ1 |
| GAP-02 | Approval bằng `Duyệt` từ hook/user prompt và hash trong SQLite cùng quyền user | Không có xác thực human privilege boundary trước agent cùng macOS UID — Đ2 |
| GAP-03 | File leases TTL 120s được dọn theo thời gian, chưa thấy fencing/heartbeat an toàn trên mọi mutation | Nguy cơ stale writer; cần atomic compare-and-apply — Đ2/Đ5 |
| GAP-04 | Hook config bao phủ một số event nhưng bản thân hook không phải OS enforcement | Capability certification riêng mỗi app+OS — Đ2 |
| GAP-05 | Source Preview đã có task/contract/guard logic nhưng không có RIG 8 trách nhiệm semantic end-to-end | Xây RIG tích hợp và Navigator — Đ3 |
| GAP-06 | Thiếu canonical Plan + Work DAG gắn versions/profile/domain | Xây planner/policy resolver — Đ4 |
| GAP-07 | Chưa có Task Change Manifest và Git-index transaction theo task | Xây controlled mutation — Đ5 |
| GAP-08 | Verification hiện tại chạy theo config tùy chọn, chưa có evidence dependency graph | Xây verification/freshness — Đ5 |
| GAP-09 | Chưa có reviewer/convergence/DoD thực thi theo SPEC | Xây review/DoD — Đ5/Đ6 |
| GAP-10 | Chưa có chứng nhận thực tế 4 bề mặt Codex/Claude macOS | Chứng nhận Đ2/Đ5/Đ7 |
| GAP-11 | `README.md` Preview gợi ý `Tiếp tục T-...` trong một số tình huống | Task Navigator tự khôi phục/định danh, không bắt user nhớ ID — Đ3 |
| GAP-12 | User docs trong Preview mô tả cơ chế chưa chốt/thực thi, không phản ánh baseline mới | Viết lại hai hướng dẫn theo mã được nghiệm thu — Đ7 |

**Giới hạn quan sát:** Gap list chỉ đánh giá source Preview và thử nghiệm unit đã chạy. Chưa thể kết luận chính xác về mọi bản Codex/Claude GUI trên Mac của bạn.
