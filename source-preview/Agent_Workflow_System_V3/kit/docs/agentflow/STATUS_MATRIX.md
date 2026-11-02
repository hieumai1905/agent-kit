# Ma trận đáp ứng yêu cầu — trạng thái kỹ thuật thực tế

| Quyết định | Người dùng đã chốt | Đã có trong kit | Chưa được chứng minh / cần làm tiếp |
|---|---|---|---|
| D1 | B: Strict Approval có kiểm soát ghi | Contract hash, in-chat approve, PreToolUse deny, scope check | Hard OS permission boundary cho *cả bốn GUI/CLI* |
| D2 | Duyệt thuận tiện trong chat | `Duyệt` trong đúng session, đúng proposed fingerprint | Xác thực thao tác của user trước agent có cùng OS UID; xác minh user đã thật sự nhìn full SPEC |
| D3 | B: concurrent writers trên cùng working tree | SQLite resource leases, disjoint files có thể qua hook | Cô lập side effects, Git index, files phụ thuộc logic, hooks không intercept; hard arbitration |
| D4 | A: Model advisor | Tier scoring, per-provider allowlist/known list/usage_mode | Live catalog & usage sync vào hai tài khoản trên GUI; đánh giá model mới tự động |
| D5 | B: Risk-adaptive checks | Schema và runner theo danh sách check đã cấu hình | Test pipeline và tiêu chí quality riêng của repo chưa chốt |
| D6 | A: Per repository | Installer merge+backup+dry-run | Chưa cài trên macOS/repo của user |
| Prompt normalization | Read-only + user approval | Tự tạo task, contract template, validation, propose | Semantic intent classifier/scoping/risk confidence chưa chốt và chưa được benchmark |
| Multi-session continuity | Cùng task qua nhiều session | `Tiếp tục T-ID`, SPEC/STATE + Git diff guide | Real-life crash/handoff test trong app chưa chạy |
| Coding standards | Chưa thảo luận sâu | Conservative policy: follow existing conventions | Coding style, architecture, naming, test pyramid và automation rules theo project |

**Kết luận:** V3.0 preview là **bộ nền tảng chạy được và cấu trúc để tiếp tục thiết kế**. Không được gọi là toàn bộ V3.0 đã đạt yêu cầu an toàn hay tối ưu cho repo thật.
