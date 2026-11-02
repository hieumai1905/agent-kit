# MỤC TIÊU & QUYẾT ĐỊNH KHÓA PHẠM VI — PRACTICAL AGENT WORKFLOW V3

**Điều khoản ưu tiên tối cao:** Đây là một **bộ hỗ trợ quy trình coding**, KHÔNG phải một sản phẩm ứng dụng, platform, GUI, daemon, AI agent riêng hay dashboard. Phải đơn giản, tích hợp repo và test sớm. Khi tài liệu lịch sử khác câu chữ với file này về phạm vi thực dụng hiện tại, ghi khác biệt để người dùng quyết định, không tự mở rộng.

## A. Mục tiêu người dùng

1. Làm việc trong **Codex Desktop, Codex CLI, Claude Desktop tab Code, Claude Code CLI**, không cần UI khác. Dùng terminal/CMD khi dùng CLI; dùng giao diện app sẵn có khi dùng Desktop.
2. **Một local repo, một working tree**, có nhiều task/session. Session/code agent có thể khác nhau; tasks/state sống qua phiên và không cần transcript dài.
3. Giao task ngôn ngữ tự nhiên. Agent tự tìm task và ngữ cảnh, tự phân loại độ sâu, chỉ hỏi những quyết định sản phẩm/rủi ro thật sự cần hỏi.
4. Agent làm **Requirement Intelligence Gate (RIG 8)**, trình Task Contract nhỏ gọn có scope/acceptance. **D1–D2** Strict Approval và thuận tiện trong hội thoại là yêu cầu; không đồng nhất prompt/chat approval với chứng thực native đã có.
5. Sau approval, **Execution Engineering Workflow (EEW 10)** lập plan đúng scope, code theo standards phù hợp, test, review, handoff/DoD. Người dùng có thể tự đổi model/provider; model advisor chỉ đề xuất.
6. Đúng ý, simple, concise, maintainable; Quick/Standard/Deep vừa đủ, không hàng chục file/report không cần thiết, không buộc subagents.
7. Không tự commit/push/deploy, nâng quyền, tạo secrets, gửi dữ liệu nhạy cảm, cài hooks/GUI/daemon hay sửa repo khác khi chưa có sự đồng ý riêng.

## B. Quyết định D1–D6 đã chốt

- **D1:** Strict Approval trước product code changes và thực thi có quyền thật (chưa chứng nhận).
- **D2:** Phê duyệt thuận tiện ngay trong hội thoại của công cụ đang dùng; không bắt chạy lệnh riêng cho mỗi task.
- **D3:** Nhiều agent/session có thể làm việc song song trên các resources độc lập cùng working tree; cần coordination và bằng chứng, không chỉ file lock.
- **D4:** Model Advisor chỉ khuyến nghị; user tự chọn model và chuyển Codex/Claude.
- **D5:** Quality Gate adaptive theo risk/Quick–Standard–Deep, evidence-based.
- **D6:** Cài theo từng repo, có dry-run, backup, rollback và không phá config cũ.

## C. Các bộ yêu cầu khác

- RIG: **8 trách nhiệm** gồm Intent, Discovery, Impact, Scenarios, Gaps, Clarification, Challenge, DoR/Approval; A01–A10 đã chốt.
- EEW: **10 chuyên đề** gồm Activation, Technical Plan, Work Graph, Core Coding Standards, Domain Standards, Controlled Coding, Verification, Review, DoD/Handoff, Model/Context/Usage. D04–D10 đã chốt ở mức thiết kế.
- SI01–SI14: người dùng đã chỉ định **triển khai** trong lượt trước; đã có lớp draft/diagnostics và tests ở mức local, chưa native-certified.
- EA01–EA16: **tạm gác phạm vi phát triển**, không xóa phá code hiện có nhưng không chủ động mở rộng.

## D. Hai chế độ minh bạch cho giai đoạn chưa chứng nhận G2

- `STRICT`: mặc định không cho kit hướng dẫn agent ghi product code; đọc, phân tích, lập nháp/handoff.
- `ADVISORY`: opt-in rõ ràng để thử coding trong repo qua provider tools hiện có sau chat-level approval; **không đáp ứng D1 hard enforcement**. Hãy dùng thử trong repo an toàn/giả lập. Chế độ này không tự được bật khi chỉ nói “Duyệt”.

**Không được làm sai lệch:** STRICT chưa được thực thi ở cấp OS bởi kit; nó là chỉ dẫn fail-closed. Không thay đổi D1 thành 'soft approval là đủ' chỉ vì cần dùng sớm. Ngược lại, không được tự phát triển thêm SwiftUI/native Guard.app để giải quyết G2 khi chưa được người dùng chốt phương án.

## E. Scope giới hạn và tiêu chí không-scale

- Một hướng dẫn cốt lõi ở `AGENTS.md` + một tham chiếu ngắn ở `CLAUDE.md`.
- Python CLI hỗ trợ read-only/state ngoài repo; không phải bước bắt buộc mỗi task.
- Không thêm frontend, service, server, REST API, telemetry cloud, planner thứ hai, subagent orchestration, cấu trúc nhiều worktrees hoặc bộ tài liệu nặng trong repo.
- Nếu một tính năng khó có proof, giữ NOT_CERTIFIED/PARTIAL và đưa vào báo cáo phương án xử lý nhỏ thay vì cố xây cả tầng kiến trúc.
- Đánh giá bằng **một task Quick coding thật trên repo giả**, thời gian từ prompt đến diff/test hữu ích, số lượt hỏi lại, chất lượng handoff, số file kit ảnh hưởng, khả năng rollback; chưa có đo thực tế, không đặt chỉ số tiết kiệm tự suy.
