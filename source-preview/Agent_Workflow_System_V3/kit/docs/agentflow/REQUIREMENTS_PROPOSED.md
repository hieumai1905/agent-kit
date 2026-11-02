# Requirement Engineering Gate — ĐỀ XUẤT, chưa chốt logic sâu

## Nguyên lý

Không đánh đồng **prompt trông chuyên nghiệp** với **yêu cầu đã hiểu đúng**. Prompt gốc được bảo tồn, mọi mục tiêu/bổ sung đều phân biệt: (a) User confirmed, (b) Observed from repo, (c) Assumption, (d) Unknown. LLM tự tìm sự thật trong repo ở chế độ read-only; script chỉ xác minh schema, hash và chuyển bước, không thay thế hiểu ngữ nghĩa.

## Quy trình đề xuất

1. **Intent classification:** câu hỏi/thảo luận, tạo task mới, tiếp tục task, thay đổi scope, giải thích kết quả. Nếu có nhiều task và không rõ task nào, đề nghị xác nhận, không đoán.
2. **Repository reconnaissance (read-only):** đọc README, lệnh chạy, source, test liên quan, dependency boundary; không mở hàng trăm file một cách mù quáng.
3. **Goal reconstruction:** diễn đạt thành kết quả mong muốn có thể kiểm chứng, không phải chuỗi công việc kỹ thuật thiếu đích.
4. **Evidence & ambiguity:** phân biệt điều xác minh được, giả định hợp lý, câu hỏi còn thiếu, mâu thuẫn và rủi ro.
5. **Acceptance criteria:** mô tả đầu ra/behavior/negative cases; chỉ thêm yêu cầu có căn cứ, không tự thêm tính năng.
6. **Proposed scope:** module/file globs dự kiến; xét phụ thuộc/shared resources; ngoài scope chỉ mô tả, không tự sửa.
7. **Risk & complexity:** suy luận từ tác động/hệ quả, không chỉ số file; khi payment/auth/migration/security thì yêu cầu review tăng cường.
8. **Spec presentation:** render thành `SPEC.md`, nêu ngắn trong chat mục tiêu, phạm vi, non-goals, test, câu hỏi đã được giải quyết, rủi ro; cho user duyệt.
9. **Change control:** câu “sửa thêm X” chưa phải phần đã duyệt; nếu tác động mục tiêu/scope/acceptance thì revise spec + duyệt lại.

## Những câu hỏi chỉ nên hỏi người dùng

- Mục tiêu sản phẩm có nhiều cách hiểu và lựa chọn ảnh hưởng kết quả.
- Thay đổi UI/UX chủ quan không có thiết kế tham chiếu/tiêu chí rõ.
- Chấp nhận rủi ro phá vỡ tương thích, xóa dữ liệu, thay đổi schema hoặc secrets.
- Scope có thể ảnh hưởng nhiều task, cần ưu tiên/phê duyệt tác động.

Không hỏi user những thứ có thể đọc được từ code, package manager, test config hoặc tài liệu repo.

## Contract schema hiện đang dùng

```json
{
  "objective": "...",
  "scope": ["src/auth/**", "tests/auth/**"],
  "out_of_scope": ["src/payments/**"],
  "acceptance": ["Một hành vi quan sát và kiểm chứng được"],
  "verification": ["Tên test/kiểm chứng dự kiến"],
  "risk": "LOW|MEDIUM|HIGH",
  "complexity": "LOW|MEDIUM|HIGH",
  "assumptions": [],
  "open_questions": [],
  "impact": "..."
}
```

Các trường thiếu/placeholder/open_questions chặn propose. Script *không* chứng minh rằng acceptance criteria đúng ý user; Strict Approval bù đắp một phần nhưng user phải review thật.

## Trường hợp cần chốt tiếp

- Tiêu chuẩn bao nhiêu thông tin được xem là đủ để đề xuất spec?
- Câu hỏi UI chủ quan cần minh họa thế nào trước duyệt?
- Phân loại task mới/phụ trong cùng một session dựa vào model thế nào để tránh tạo nhầm task?
- Có cần chốt nguyên nhân gốc trước khi đề xuất sửa bug, hay cho phép phê duyệt một pha điều tra riêng?
- Spec nào nên chia thành milestones, subtask và acceptance riêng?
- Có nên có confidence threshold, và dựa trên bằng chứng nào?

**Khuyến nghị của bộ kit:** chưa thiết lập hard threshold “confidence 80%”. Không có cơ sở hiệu chuẩn, dễ tạo tự tin giả.
