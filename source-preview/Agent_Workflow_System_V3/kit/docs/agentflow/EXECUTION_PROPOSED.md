# Execution Engineering Policy — ĐỀ XUẤT, chưa chốt conventions

**Mục tiêu phiên thảo luận tiếp:** chốt hành vi coding agent sau khi Task Contract đã được duyệt. Những quy tắc dưới đây là default bảo thủ, không phải code style tối ưu cho mọi repo.

## A. Trước khi sửa code

- Đọc SPEC.md, STATE.md, các module liên quan và Git diff.
- Xác minh những thay đổi đang dang dở do session khác; tuyệt đối không xóa hoặc overwrite để “clean”.
- Kiểm tra scope do preflight đề xuất, phụ thuộc, shared resources, test hiện có.
- Chỉ triển khai nội dung SPEC đã được user duyệt; nếu cần đổi kiến trúc/phạm vi phải quay lại preflight.

## B. Style/Conventions mặc định

- **Existing conventions win:** không bắt dự án TypeScript/Go/Rust/Python phải cùng một style.
- Không tự tạo framework mới, pattern mới hoặc cấu trúc thư mục mới khi code hiện tại đã có pattern phù hợp.
- Không tự thêm dependency hoặc đổi version lớn khi chưa có lý do/phê duyệt.
- Giữ changeset tập trung; tránh formatting lan rộng làm khó diff/review.
- Ưu tiên tên hàm/biến diễn đạt mục đích và hành vi hơn comment dài.
- Không thay đổi API contract, DB schema, auth/permission boundary hoặc cách deploy nếu SPEC không cho phép.
- Không tạo tính năng “tiện ích” ngoài scope, không lén sửa unrelated bugs.

## C. Iteration & Verification

- Thực thi theo những bước có thể kiểm chứng; mỗi bước có mục tiêu, thay đổi và bằng chứng.
- Kiểm thử tính đúng trước tối ưu; không chấp nhận test giả/sửa assert để che lỗi.
- Chạy test liên quan trước test rộng nếu thời gian/usage hữu hạn; chất lượng/độ rủi ro quyết định mức test tối thiểu.
- Nếu test fail: phân tích nguyên nhân gốc, phân biệt lỗi sẵn có, ghi bằng chứng; sau hai lần sửa không tiến triển thì đánh giá lại, không lặp mò.
- Không báo PASS nếu không chạy; nếu thiếu môi trường ghi NOT RUN và lý do.

## D. Review & Finish

- Review git diff, phạm vi, tiêu chí acceptance, regression, rủi ro bảo mật.
- Báo thay đổi thực tế, kiểm tra đã chạy/chưa chạy và tồn đọng.
- `STATE.md` chỉ lưu checkpoint hữu ích: completed, decisions, evidence, next action, blocker.
- Commit, push, deploy, publish và migration có tác động ngoài repo là các quyền riêng; không tự thực hiện.

## E. Những lựa chọn coding style cần chốt theo dự án

1. Tech stack và kiến trúc: modular monolith / clean / hexagonal / feature-based / layered?
2. File size, function complexity và mức tách module.
3. Error handling, logging, tracing, retry/idempotency.
4. Transaction boundary, schema migration & backward compatibility.
5. Test pyramid, mocking policy, E2E/test data, quality gates trước merge.
6. Frontend UI consistency, component hierarchy, accessibility, responsive targets.
7. Cách tối ưu token/context, batch reads, tránh thừa agent commentary.
8. Cách chốt “done” khi có test thiếu và manual verification.
9. Khi nào cho phép refactor ngoài scope sau khi thấy tech debt.
10. Quy tắc an ninh, dependency licenses, secrets & privacy.

Chưa đưa các quy định cụ thể của từng repo vào AGENTS.md để tránh áp đặt trước khi người dùng chốt.
