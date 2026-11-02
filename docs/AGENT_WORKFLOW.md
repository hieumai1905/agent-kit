# Workflow theo mức công việc

Chỉ dẫn nền trong AGENTS.md/CLAUDE.md chọn luồng; chi tiết payload ở USAGE.md. Giữ các quyết định người dùng và giới hạn provider hiện có. Kit là ADVISORY, không có trusted approval adapter hay OS write confinement.

1. Hỏi/đọc/nghiên cứu: khảo sát phần liên quan và trả lời. Không lập task triển khai hoặc checkpoint cho từng câu hỏi độc lập.
2. Việc nhỏ rõ: đọc code/Git vừa đủ, xác minh triệu chứng nếu sửa bug, trình contract 4–7 dòng. Chờ duyệt đúng revision, lưu/readback quyết định trước patch. Agent dùng work start/checkpoint/finish để xử lý metadata.
3. Việc mơ hồ/phức tạp: đọc bằng chứng trước, phân biệt confirmed/observed/proposed; hỏi về lựa chọn ảnh hưởng sản phẩm còn thiếu. Không tự đặt ngân sách/model-call limit hoặc chính sách sản phẩm để lấp chỗ trống. Contract phải ghi outcome, scope/exclusions, preserve, acceptance, verification và blocker. Hỏi đã được trả lời không lặp lại.
4. Triển khai: kiểm điều kiện hiện tại và recheck trước từng đợt tác động. Một writer; giữ thay đổi có trước. Guard lỗi/không rõ phải dừng. Đổi phạm vi hoặc acceptance cần quyết định tương ứng. Không tự dependencies, migrations, model/settings, Git publication hay agent phụ.
5. Debug/review: đọc VERIFICATION.md khi cần. Test sát ảnh hưởng, kiểm triệu chứng và preservation, actual exit/output và source đúng thời điểm. Thiếu kiểm chứng phải báo thiếu; reported verification luôn unverified trong runtime. Người dùng quyết định nghiệm thu.
6. Continuity: checkpoint theo quyết định, thay phạm vi, verification và handoff; không lưu mỗi message. Resume --compact chỉ đọc, history truy vấn riêng. Đối chiếu contract/source/Git và quyết định current provider; state không khôi phục quyền. Missing/truncated/unreadable không được diễn giải thành PASS.
7. Local-only: setup quản lý inventory và Git local exclude hẹp. Artifact vận hành ngoài product tree; artifacts check đọc INDEX trước handoff và trước/sau staging được duyệt riêng. Tracked/mixed guidance dừng để xử lý rõ. Không có commit hook cưỡng chế; không tuyên bố bảo vệ tuyệt đối.

Nguyên tắc đã có trong v1.0.2 được giữ. Legacy commands/state vẫn đọc được; protocol H/D, SI và model-advice chỉ dùng khi có nhu cầu/phạm vi riêng. Không biến một sự cố mới thành quy tắc always-on nếu một fix/test đúng chỗ đã giải quyết được.
