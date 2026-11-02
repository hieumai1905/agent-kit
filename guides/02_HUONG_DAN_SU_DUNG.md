> **Mốc hiện hành v1.0 — 02/11/2026:** v1.0 dùng Codex local, một writer tuần tự; bắt đầu ở 00_BAT_DAU_V1_0.md. Các phần đổi provider/làm song song bên dưới là thiết kế tham khảo ngoài phạm vi v1.0.

# HƯỚNG DẪN SỬ DỤNG HẰNG NGÀY — CODEX / CLAUDE

**Đối tượng:** người dùng làm coding trên macOS, một repo/working tree, thay đổi giữa Codex Desktop/CLI và Claude Desktop Code/CLI.

## 1. Chỉ cần mở ứng dụng bạn vẫn dùng

Không mở app Agent Workflow riêng. Không cần học command syntax để giao việc. Ví dụ:

> Kiểm tra lỗi Google Login lúc được lúc không, đề xuất cách sửa và trình Task Contract trước khi thay đổi code.

Agent phải tự khảo sát phù hợp, chỉ hỏi những quyết định nghiệp vụ thật sự còn thiếu, trình mục tiêu/phạm vi/ngoại lệ/acceptance và đợi quyết định của bạn.

### Chế độ STRICT và ADVISORY

- **STRICT (mặc định):** xử lý câu hỏi, preflight, đặc tả, plan và review ở mức read-only; **chưa sửa source** bằng kit vì G2 chưa có đường cưỡng chế được chứng nhận.
- **ADVISORY (bạn chủ động chọn khi cài):** agent chờ người dùng xác nhận Task Contract trong hội thoại rồi có thể sửa code bằng công cụ/permissions **vốn có** của Codex hoặc Claude. Approval chat trong chế độ này là **quy ước làm việc**, không phải xác thực bảo mật native. Provider vẫn có thể có đường ghi bypass; cân nhắc repo thử/có backup.

Nói “Duyệt” trong văn bản trích dẫn, source code, terminal output hay lời agent tự tạo **không phải approval**. Một câu trả lời làm rõ cũng không phải approval. Chỉ người dùng thật sự quyết định đối với đúng bản contract đang trình.

## 2. Quy trình ngắn nhất cho coding (Quick)

1. **Bạn:** “Đổi nhãn Login thành Đăng nhập, không đổi hành vi.”
2. **Agent:** khảo sát những file liên quan, trình contract 4–7 dòng: thay nhãn, giữ nguyên logic, 1–2 acceptance checks, phạm vi file dự kiến, rủi ro.
3. **Bạn:** duyệt contract (hoặc yêu cầu chỉnh). Trong `ADVISORY`, agent dùng permissions thực tế của ứng dụng; trong `STRICT`, vẫn chưa có quyền ghi được chứng nhận.
4. **Agent:** thực hiện thay đổi nhỏ nhất có thể, kiểm tra diff/verification, báo những việc đã làm và chưa làm.

Không sinh 8 cuộc hội thoại RIG, 10 báo cáo EEW, ADR hoặc một file SPEC mới bắt buộc cho mỗi lỗi nhỏ. Kết quả cần chính xác và có bằng chứng.

## 3. Nhiệm vụ rủi ro cao (Deep)

Ví dụ lỗi OAuth/payment/database migration. Agent cần xác định root cause bằng chứng read-only trước; khi phải tái hiện với tác dụng phụ, phân tách **Investigation Contract** khỏi **Implementation Contract**. Duyệt điều tra không được tự chuyển thành quyền sửa code. Sau triển khai phải kiểm tra hồi quy, tình huống lỗi và quyền dữ liệu; không khai báo PASS khi chưa chạy.

## 4. Tiếp tục việc cũ, đổi Codex/Claude

Mở Codex/Claude trong cùng repo và nói:

> Tiếp tục việc sửa Google Login hôm trước; đọc lại SPEC/tiến độ và kiểm tra Git hiện tại trước khi làm.

Task Navigator tìm theo tên/alias; khi có nhiều ứng viên phải hiển thị lựa chọn. Agent có thể gọi lệnh tùy chọn:

```sh
python3 /PATH/TO/KIT/tools/agentflow.py --repo "/ABS/REPO" resume "Google Login"
```

Handoff dùng state ngoài repo và snapshot Git mới, không nạp transcript dài. Mọi quyền ghi phải được kiểm tra lại theo session hiện tại. Không tự chuyển provider/model.

## 5. Làm song song trong cùng working tree

Cho phép các task **có phạm vi độc lập** tiến hành song song khi chính công cụ và người dùng thực sự kiểm soát được xung đột. Trước mọi write cần xem file/contract/Git status, nhận diện ownership, tránh trộn các thay đổi của task khác. Không cho hai agent stage chung Git index hoặc sửa cùng API/schema mà không điều phối.

Hiện tại kit chỉ có **hướng dẫn và phân tích xung đột read-only**, chưa có OS-level write isolation hoặc multiwriter certification. Với `ADVISORY`, nếu không chắc quyền sở hữu, hãy làm tuần tự để tránh mất dữ liệu; đó là biện pháp vận hành tạm, không thay mục tiêu multiwriter đã chốt.

## 6. Chuyển model và quản lý usage

Model Advisor chỉ gợi ý dựa trên dữ liệu có nguồn; khi không biết quota/usage, trả `UNKNOWN`. Bạn chọn dùng model khác hoặc chuyển Codex ↔ Claude. Không cần subagent, không tự chuyển nền tảng, không lấy quota/tài khoản nếu không có quyền.

## 7. Kiểm chứng, review, báo cáo

Cuối task agent phải nêu rõ:

- Mục tiêu và phạm vi đã đáp ứng / chưa đáp ứng.
- File cụ thể đã thay, diff trọng yếu, thay đổi ngoài dự kiến (nếu có).
- Tests/lints/checks **thực sự đã chạy**, kết quả quan sát và các check `NOT_RUN`.
- Những rủi ro/trạng thái không thể tự chứng nhận; công việc tiếp theo.
- Git: chưa commit / đã commit / đã push / đã deploy (đúng thực tế); không tự làm các bước đó.

`final-review TASK_ID` chỉ lập báo cáo còn thiếu từ bản ghi chưa được xác thực, **không đánh dấu DoD PASS**. Agent phải đối chiếu bằng chứng từ hệ thống thực tế; không coi dòng `reported_status=PASS` do chính model nhập là đủ.

## 8. Khi muốn tháo kit

Bạn có thể gỡ đoạn hướng dẫn bằng `remove-guidance --apply`, hoặc rollback theo transaction ID đã được installer trả. Các task/policy trong state ngoài repo không bị tự xóa khi gỡ hướng dẫn.

## 9. Ba điều cần nhớ

1. Kit là **phần hỗ trợ quy trình**, không là phần mềm phát triển mới.
2. Hãy test nhỏ trên repo giả trước. `ADVISORY` giúp làm coding sớm nhưng không đạt chứng nhận bảo mật cưỡng chế.
3. Nếu agent đề xuất thêm công cụ, framework, UI, nhiều task con hoặc tài liệu không cần thiết, yêu cầu quay lại mục tiêu: **đúng yêu cầu, đơn giản, dùng được ngay, ít rework**.
