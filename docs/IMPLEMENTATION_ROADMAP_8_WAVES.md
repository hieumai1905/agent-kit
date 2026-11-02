# KẾ HOẠCH TRIỂN KHAI 8 ĐỢT — AGENT WORKFLOW SYSTEM V3.0

**Baseline:** 29/10/2026 · **Trạng thái:** Execution approved; Đ0 đang thực hiện; Đ1–Đ7 chưa nghiệm thu.

## 1. Kết quả phải bàn giao

- **Integration Kit:** Bộ cài local macOS có installer dry-run/apply/doctor/upgrade/rollback/uninstall, Local Coordinator, canonical state, trusted approval, adapter Codex Desktop/CLI và Claude Desktop Code/CLI, Task Navigator, RIG, EEW, Engineering/Domain Profiles, verification, handoff.
- **Integration & Setup Guide:** Điều kiện macOS, quyền, cấu hình bốn bề mặt, cài/kiểm tra từng repo, cấu hình Engineering Profile, trạng thái hoạt động, cập nhật/rollback/gỡ cài, khắc phục lỗi và giới hạn phiên bản.
- **User & Operations Guide:** Giao task bằng ngôn ngữ tự nhiên, xem/chỉnh Task Contract, duyệt, tiếp tục, đổi Codex/Claude thủ công, model advice, nhiều task/session, lỗi, chặn an toàn, kết quả/DoD, Git và troubleshooting.
- **Bằng chứng phát hành:** Acceptance report, adapter capability matrix theo app/build/OS, test runner, code/config hashes, known limitations. Đây là hồ sơ kèm bộ kit.

**Ràng buộc bất biến:** Một local repo và một working tree; đa task/đa session; không tự chuyển model/nền tảng; không bắt người dùng nhập Task ID/scope; không subagents bắt buộc; không sửa product code trước verified approval; không commit/push/deploy ngầm; code Simple, Concise & Maintainable, patterns theo nhu cầu; Quick/Standard/Deep đủ chất lượng mà không tạo overhead.

## 2. Cổng nghiệm thu và tám đợt

### Đ0 — Đóng băng thiết kế, đối chiếu Preview và dựng development baseline

**Xây:** Chốt register RIG(8)+EEW(10)+A01–10+EA01–16+SI01–14; snapshot nguồn Preview; thống kê source/test đã có; lập acceptance matrix, threat model, chỉ ra những cơ chế đang là guardrails; thiết lập bộ test chạy lại được. Không cài vào repo thật.

**Đầu ra:** baseline ZIP, design baseline, gap register, acceptance registry, source hashes, test evidence.

**G0 PASS khi:** snapshot có checksum; bộ 5 test Preview PASS; smoke test installer chỉ tác động repo tạm; không có tuyên bố sai `ENFORCED`; các hạng mục chưa chứng minh vẫn có trạng thái `NOT_RUN`/`BLOCKED`.

### Đ1 — Canonical Foundation & Local State Coordinator

**Xây:** Một schema versioned cho task, contract, approval references, session, work item, policy, lease, evidence, review, completion; SQLite transaction/migrations; audit events; runtime metadata ở ngoài working tree mặc định; deterministic state machine; registry phiên bản policy; bootstrap/migration/backup/recovery.

**Đầu ra:** core Python package/API, local data schema, CLI doctor, migration/test fixtures.

**G1 PASS khi:** transitions sai bị từ chối; recovery/crash không tạo approval giả; concurrency metadata không làm mất cập nhật; migration lên bản mới bảo toàn dữ liệu; state dir tách repo; policy/contract/hash được kiểm tra có nguồn; tests độc lập PASS.

### Đ2 — Trusted Approval + Enforced Execution Feasibility (Gate trọng yếu)

**Xây:** trusted user approval/approval revision & revocation; quyền policy admin riêng; read-only preflight; capability handshake theo adapter/app version; proof-of-enforcement: OS sandbox/write broker hoặc môi trường thực sự không có direct bypass; fencing token, symlink/path checks, unsafe tool-path tests. Phải kiểm tra thực tế macOS.

**Đầu ra:** Control Plane prototype, executor permission model, capability certificates có bằng chứng, matrix bốn bề mặt.

**G2 PASS khi:** chứng minh deny trước approval, deny sau thu hồi/khác scope, deny khi hook lỗi/không chạy và các đường shell/file/MCP bị đánh giá; không bypass được Trusted Mutation Boundary trong phạm vi tuyên bố; khôi phục session/lease an toàn. Chứng nhận riêng Codex Desktop, Codex CLI, Claude Desktop Code, Claude Code CLI, gắn macOS/app version. Nếu chưa đạt một bề mặt, đánh dấu `NOT_CERTIFIED`, không quảng bá đủ bốn adapter. Không tự hạ xuống hook guardrails mà vẫn gọi là strict.

**Điều kiện phát triển:** Có thể tiếp tục xây/simulate các lớp độc lập trong môi trường thử nghiệm, nhưng không phát hành hoặc cho chạy ghi trên repo quan trọng trước khi Gate này đạt. Nếu enforcement không khả thi ở một GUI, phải trình phương án thay đổi cách thực thi để người dùng quyết định, không tự bỏ yêu cầu.

### Đ3 — Task Navigator + RIG/Approval End-to-End

**Xây:** intent router mới/sửa/tiếp tục/hỏi/phê duyệt; task search/resume/fuzzy; RIG tám trách nhiệm trong một preflight thích nghi; knowledge provenance và gap/clarification tracking; versioned Task Contract và DoR; phương án Investigation Contract khi cần thao tác có side effects; profile bootstrap ở setup đầu tiên.

**Đầu ra:** read-only discovery, Task Navigator, draft/propose/approve/revise/resume flow, UX chat/CLI adapter protocol.

**G3 PASS khi:** không sinh task trùng vô nghĩa; không cần user nhập ID/scope; một câu trả lời làm rõ không được coi là approval; approval chỉ hợp lệ cho revision duyệt; trước duyệt không có product changes; repo text không thể nâng quyền; sessions đồng bộ quyết định; Quick preflight không phình token.

### Đ4 — EEW Planning + Engineering/Domain Profile Resolver

**Xây:** adaptive Technical Plan + Work DAG, consistency/incremental replanning; Repository Engineering Profile one-time approval; domain rules per stack/task/risk; profile/version/exception management; style Simple–Concise–Maintainable, patterns khi cần; tool-config checkers.

**Đầu ra:** planner/scheduler, policy resolver, repo bootstrap templates, architecture/coding and domain profile adapters.

**G4 PASS khi:** plan không tự đổi SPEC, work DAG không có cycle, ownership/deps rõ, thay đổi plan chỉ invalidate phần liên quan; Quick không sinh tài liệu thừa; không ép design pattern/framework mới; policy chỉ nạp relevant; profile được duyệt và dùng lại qua session.

### Đ5 — Controlled Mutation + Verification + Review (Gate trọng yếu)

**Xây:** trusted atomic compare-and-apply; task-scoped Change Manifest, file/contract/resource leases, heartbeat/fencing, Git index governance; tool effects registry; test resource isolation, evidence freshness, failure recovery; code health + spec convergence checks.

**Đầu ra:** Mutation Boundary, task-scoped change/verification/review pipeline và safe Git interface.

**G5 PASS khi:** hai session không ghi đè cùng file, không nhầm Git index; concurrent changes các file khác cùng contract được phối hợp; stale/grant revoked fails closed; tests không phá database/ports của nhau; test PASS bị invalidate khi code liên quan đổi; review không trộn thay đổi task khác; missing acceptance criterion không báo PASS; chứng nhận lại trên macOS thực tế.

### Đ6 — Definition of Done + Handoff + Model/Context/Usage

**Xây:** DoD theo SPEC, task completion tách commit/push/deploy; task-scoped handoff/crash recovery; context packet Core/Active/Relevant/Archive; Model Advisor từ catalog đã xác nhận, usage KNOWN/ESTIMATED/UNKNOWN; local-first telemetry; workflow improvements chỉ qua quy trình duyệt policy.

**Đầu ra:** completion record, resumed sessions, model recommendation, local metrics, per-task report.

**G6 PASS khi:** session khác/CLI-GUI resume không cần transcript hoặc task ID thủ công, đúng file/commit ownership; missing test ≠ PASS; known model suggestions không được tự switch; không ước đoán usage nếu thiếu nguồn; không tự push/deploy/commit; task Completed không yêu cầu working tree sạch toàn bộ.

### Đ7 — Installer, Documentation, Cross-Provider E2E & Final Release (Gate trọng yếu)

**Xây:** installer/doctor/dry-run/apply, backup, upgrade, rollback, uninstall idempotent, config merge; hướng dẫn setup từng repo và hướng dẫn sử dụng đầy đủ tiếng Việt; Golden Workflow E2E (Quick/Standard/Deep, concurrency, approvals, crash, Git, malware prompts); capability matrix theo OS/app version; release packaging, checksum/release report.

**Đầu ra:** (1) `Integration_Kit.zip`, (2) `Integration_Setup_Guide.pdf/md`, (3) `User_Operations_Guide.pdf/md`, (4) `Acceptance_Report.pdf/md` và checksums.

**G7 PASS khi:** fresh install trong repo thử thật; setup được từng adapter được tuyên bố hỗ trợ; không ghi đè config cũ; upgrade + rollback + uninstall giữ nguyên user code; natural task→approval→implement→verify→review→DoD; parallel work + crash/handoff; positive/negative security tests trên cả bốn bề mặt; tài liệu khớp chính xác lệnh và UX đã chứng nhận; không còn BLOCKER đối với phạm vi phát hành.

## 3. Đợt nào phải nghiệm thu?

**Tất cả 8 đợt đều có nghiệm thu kỹ thuật G0–G7.** Không đẩy các lỗi quan trọng sang cuối rồi gọi là hoàn tất.

- **Điểm kiểm soát thủ công quan trọng:** G2 — xác nhận feasibility trên Mac và quyền thật; G5 — concurrency/coding/test an toàn trên repo thử; G7 — nghiệm thu toàn bộ kit + hướng dẫn. Các đợt khác có thể tự kiểm tra và trình báo cáo PASS/FAIL bằng chứng; người dùng không cần phê duyệt từng unit test.
- **Gating phụ thuộc:** G2 chưa PASS thì các khối khác có thể phát triển ở môi trường cô lập nhưng không được bật ghi trên repo thật hay gắn nhãn FINAL. G5 chưa PASS thì không nghiệm thu final multiwriter. G7 chỉ PASS nếu mọi capability đã tuyên bố đều có chứng chỉ hợp lệ.
- **Bằng chứng mỗi gate:** test case IDs, commands/tool, version, timestamp, code/source fingerprints, expected vs actual, PASS/FAIL/BLOCKED/NOT_RUN, limitations và corrective actions. Trạng thái `NOT_RUN` không bao giờ được dùng như PASS.

## 4. Chứng nhận bốn môi trường

| Môi trường | Chứng nhận tối thiểu |
|---|---|
| Codex Desktop GUI | Local repo, hooks/config, trusted approval provenance, tool paths, pre/post write, context/resume, tool escape paths |
| Codex CLI | Same repo, sandbox profiles/approval, trust boundary, change grant and atomic apply, crash/recovery |
| Claude Desktop Code tab | Local folder; xác minh có/không worktree mặc định; cấu hình chỉ dùng đúng shared working tree; hooks/permissions, write paths, parallel sessions |
| Claude Code CLI | Permission modes/hooks, shared working tree, CLI/GUI handoff, unauthorized writes and tool paths |

`CERTIFIED` chỉ khi có bằng chứng tại đúng phiên bản app + macOS + cấu hình. `NOT_CERTIFIED` nếu thiếu hoặc FAIL. Không đánh đồng hook discovery với OS-level write isolation.

## 5. Tiêu chí chất lượng sản phẩm

- Hệ thống chỉ hỏi người dùng những quyết định sản phẩm/rủi ro thật sự cần người dùng quyết. Không bắt gõ Task ID, risk, file scope, lệnh CLI cho workflow thường ngày.
- Quick task: giao→duyệt→xem kết quả, không sinh nhiều document hay model-call gate. Deep task: kiểm chứng sâu theo rủi ro.
- Không tự chọn nền tảng/model hoặc hạ mức security để tiết kiệm usage.
- Coding standards theo stack/domain; code đơn giản, gọn, dễ đọc, maintainable; design pattern chỉ khi giải quyết vấn đề thực.
- Một canonical state record, không nhân các bản sao `SPEC/STATE/PLAN` độc lập có thể mâu thuẫn.
- Final integration package phải dễ cài, dễ kiểm tra, dễ rollback; hướng dẫn setup và sử dụng là một phần của DoD release chứ không phải việc làm thêm tùy ý.

## 6. Điều kiện đầu vào cho đợt tiếp theo

G0 có thể hoàn tất trong môi trường container hiện tại với baseline, tests và ma trận khoảng trống. Để nghiệm thu G2/G5/G7 ở mức macOS GUI thật, cần có phiên bản và cấu hình của Codex Desktop/CLI, Claude Desktop Code/CLI và khả năng chạy các bài thử đối kháng trong repo thử trên máy Mac. Chưa yêu cầu người dùng cung cấp hoặc thay đổi gì trong repo sản xuất trước khi có test harness an toàn.
