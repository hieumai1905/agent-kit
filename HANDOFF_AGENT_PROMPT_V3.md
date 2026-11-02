# Prompt tiếp nhận Agent Workflow Kit v1.0.1

**1.0.1 · 02/11/2026 · V3 engine giữ nguyên.** Dán nội dung bên dưới vào chat đang làm việc với repo. Đây là hướng dẫn sử dụng, không tự là approval cho task hoặc ghi repo.

> Đọc README_START_HERE.md của kit, guides/00_BAT_DAU_V1_0.md và hướng dẫn hiện hành của repo. Bộ kit v1.0.x đã đóng băng phạm vi: Codex trên máy hiện tại, một executor ghi tuần tự, ADVISORY tự nguyện; không mở rộng chức năng.
>
> Khi nhận việc, kiểm tra Git và tìm task theo chủ đề trước. Trình contract ngắn, chỉ hỏi điều cần quyết định; sau khi có quyết định hiện hành, lưu checkpoint quyết định trước patch, kiểm thử phù hợp và bàn giao có bằng chứng. Không ghi đè thay đổi có trước. Không tự stage/commit/push/deploy, đổi dependencies, model/provider, auth, permissions hoặc cài lại guidance.
>
> Khi tiếp tục việc, đối chiếu checkpoint với contract/source/Git và quyết định hiện tại. State/handoff là UNVERIFIED, không cấp quyền. Nếu làm qua chat điều phối, dùng đúng H/D opt-in, native refresh và checkedPatchFlow trong guides/06_DELEGATED_ADVISORY.md và guides/09_CHECKED_PATCH_FLOW.md. H/D cũ đã kết thúc thì không tái dùng.
>
> Báo file thay đổi, test/check đã chạy và chưa chạy, kết quả/giới hạn, Git và bước tiếp theo. Guard lỗi phải dừng flow; không gọi patch riêng để đi tiếp. ADVISORY chưa có OS enforcement/trusted approval; không tự đổi canonical state thành APPROVED/COMPLETED.
>
> Trạng thái bản giao hiện hành ở release/V1_0_1_ACCEPTANCE.json; release/V1_0_ACCEPTANCE.json giữ kết quả v1.0 lịch sử; regression ở release/ONE_SHOT_ACCEPTANCE.json; pilot Concat ở release/A4_RETRY_ACCEPTANCE.json. A4 đầu FAIL được giữ nguyên. Tài liệu cũ trong docs/history, source-preview và các báo cáo theo mốc chỉ là lịch sử; không xem backlog cũ là lệnh triển khai. Chỉ xử lý yêu cầu thật của người dùng, tạm dừng phát triển mở rộng.

Bản handoff audit dài trước v1.0 được lưu nguyên trong `docs/history/HANDOFF_AGENT_PROMPT_V3_before_v1_0_2026-11-02.md`.
