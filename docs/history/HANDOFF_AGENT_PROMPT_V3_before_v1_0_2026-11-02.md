# MASTER HANDOFF PROMPT — AGENT WORKFLOW V3 / PRACTICAL REPO KIT

**Bàn giao ngày 29/10/2026. Dùng để dán vào một cuộc hội thoại mới với Codex/Claude hoặc một AI agent tiếp nhận.**

Bạn là **Senior Software Engineer + Practical Workflow Reviewer + Acceptance Auditor**. Hãy tiếp nhận bộ kit mã nguồn đi kèm, rà soát tính đúng đắn của việc tích hợp trong repository, phát hiện lỗ hổng và báo cáo **phương án xử lý nhỏ nhất cần thiết** với người dùng. **NHIỆM VỤ ĐẦU TIÊN CỦA BẠN LÀ AUDIT & REPORT, KHÔNG PHẢI TỰ ĐỘNG VIẾT THÊM CẢ MỘT NỀN TẢNG MỚI.**

## 0. ƯU TIÊN CAO NHẤT — TINH THẦN SẢN PHẨM

**Agent Workflow V3 KHÔNG phải một phần mềm, platform, GUI, service hay ứng dụng AI mới.** Nó chỉ là bộ quy tắc, công cụ Python nhỏ, tệp hướng dẫn repo, state và các tiêu chí kiểm tra nhằm hỗ trợ người dùng làm việc với AI coding agents **chuẩn hóa hơn, chính xác hơn, giảm rework và tối ưu hiệu suất**. Ưu tiên **test sớm, dùng được ngay trong repo**, không scale quá lớn, không chạy theo features chỉ vì tài liệu từng đề cập.

**Các giao diện người dùng DUY NHẤT:** Codex Desktop, Codex CLI, Claude Desktop (tab Code), Claude Code CLI. Người dùng thao tác bằng chat trong Desktop hoặc terminal/CMD trong CLI; **không tự tạo app/UI/SwiftUI/dashboard/Control Plane UI**. Không yêu cầu subagent. Dùng cùng một local Git repository và một working tree. Model/provider do người dùng tự chuyển.

**Không tự đổi mục tiêu:** Khi phát hiện mâu thuẫn giữa “strict security” và “dùng coding sớm”, hãy tách rõ `STRICT` vs `ADVISORY`; giải thích trade-off và để user quyết định. Không âm thầm nâng `ADVISORY` thành chứng nhận bảo mật.

## 1. QUÁ TRÌNH VÀ CÁC MỐC ĐÃ XẢY RA

- **28/10/2026:** từ workflow trao đổi Codex ↔ Claude, người dùng muốn một hệ thống hỗ trợ làm việc trên Mac cùng một repository; ưu tiên đúng yêu cầu, không lệ thuộc hội thoại dài/usage, không tự đổi provider/model, chuẩn hóa coding process.
- **28–29/10:** xây và review thiết kế **RIG 8 trách nhiệm + A01–A10**; Task Navigator không bắt nhớ Task ID, Adaptive Preflight, versioned Task Contract, gap/evidence/decision tracking, Strict Approval, Context Lifecycle. Design Baseline V1.1 làm rõ D1–D6 và luồng giao tiếp từng pha.
- **29/10:** hoàn thiện thiết kế **EEW 10 chuyên đề**, quyết định coding policies D04/D05/D06/D07/D08/D09/D10, gồm Technical Plan, Work DAG, domain standards, implementation, testing/review, DoD, handoff, model/context/usage. **EA01–EA16** được nêu trong thiết kế cũ nhưng **người dùng đã yêu cầu tạm gác việc triển khai thêm**.
- System Integration Review đề xuất **SI01–SI14**. Sau đó người dùng yêu cầu triển khai, tạo **SI Development Candidate**, 297 bài regression + 5 Preview = 302 bài local; thêm lớp SI cho trusted-boundary diagnostics, capability observations, scoped mutation prechecks, Git previews, session fencing, evidence graph, policy exception, risk action approval proposals, footprint checks và release doctor. Không có native mandatory enforcement.
- Trước đó, Đ0–Đ2.1 có canonical SQLite state, approval receipt verifiers, hardened scratch mutation labs và nhiều tests. **Lỗ hổng hardlink alias bypass** được tái hiện trong Mac synthetic lab; kiểm thử Python không đủ chứng nhận OS security. G2 vẫn BLOCKED.
- **RC.1** đã có Đ3–Đ7 prototype/draft, 239/239 local tests PASS theo baseline cũ; G3/G4/G6 PARTIAL, G5 BLOCKED, G7 PARTIAL. Đã từng bàn giao gói ZIP dài hạn nhưng đây vẫn chỉ là candidate.
- **29/10/2026 bản practical này:** người dùng yêu cầu triển khai tiếp Đ3–Đ7 **nhưng KHÔNG mở rộng thêm kiến trúc**, tập trung **tích hợp repo để coding sớm**, giao kit đầy đủ, tài liệu, prompt và báo cáo hiện trạng để agent mới audit. Bản này thêm `STRICT` mặc định, `ADVISORY` opt-in, installer chỉ managed `AGENTS.md`/`CLAUDE.md`, rollback, natural resume, Git status, honest final-review và scratch smoke 20 bước. Hiện tại 312/312 regression + 5/5 Preview = **317/317 PASS local**, 9/9 scratch baseline smoke, 20/20 practical scratch E2E. Chưa chạy app provider thật trong container Linux.

## 2. QUYẾT ĐỊNH D1–D6 (CHỐT Ở MỨC THIẾT KẾ)

1. **D1 Strict Approval:** trước product code changes cần Task Contract/SPEC đúng revision được user duyệt và quyền ghi thực sự được kiểm soát. `READY != APPROVED != AUTHORIZED`. Yêu cầu này **chưa được chứng nhận native**.
2. **D2 Phê duyệt tiện lợi từ hội thoại:** user duyệt ngay trong Codex/Claude, không phải mở app khác hoặc gõ lệnh CLI phê duyệt thủ công. Câu chat “Duyệt” là ý định, **không tự chứng minh nguồn người thật**.
3. **D3 Multi-session/multiwriter trên một working tree:** các task độc lập có thể song song khi an toàn. Phải xử lý file/resource/contracts/Git shared state; chưa có enforcement chứng nhận. Không thay mục tiêu bằng nhiều worktrees hoặc single-writer vĩnh viễn.
4. **D4 Model Advisor:** chỉ khuyến nghị, người dùng tự quyết model/provider, usage không có nguồn là `UNKNOWN`, không phụ thuộc subagent.
5. **D5 Quality Gate adaptive:** Quick/Standard/Deep; kiểm thử, review, evidence theo risk, không báo PASS khi chưa quan sát; tránh quá nhiều bước/tài liệu.
6. **D6 Installer theo repo:** dry-run, giữ nguyên existing config, backup, upgrade/rollback/uninstall, không cài bừa hooks/settings, rollback có thể kiểm tra.

## 3. RIG 8 + A01–A10 (KHÔNG THÊM BƯỚC MỚI)

**RIG-01** Intent & Outcome; **02** Adaptive Repository/Context Discovery; **03** Impact & Dependencies (tách Change/Impact/Verification/Coordination Scope); **04** Scenario & Edge Cases (IMPLEMENT/PRESERVE/VERIFY/CLARIFY/OUT_OF_SCOPE); **05** Assumption/Gap Detection; **06** Intelligent Clarification, gắn đúng câu hỏi/task/revision; **07** Solution Challenge & SPEC Review; **08** Definition of Ready + Human Approval. Tám trách nhiệm chạy trong **một Adaptive Preflight Loop**, không 8 model calls.

**A01–A10:** multi-intent và outcome khác suggested solution; evidence provenance/freshness; technical scope envelope khác functional scope; scenario dispositions; gap ownership; clarification dedup; challenge không lặp technical planning; Investigation vs Implementation Contract; canonical task và incremental revalidation; budget/progress và verified approval được kiểm tra đúng boundary.

## 4. EEW 10 ĐÃ CHỐT

1. EEW-01 Activation/Contract Boundary.
2. EEW-02 Technical Planning/Solution Design, chọn giải pháp nhỏ nhất đủ đúng.
3. EEW-03 Work DAG/Scheduling, deps/ownership/resource và phối hợp concurrency.
4. EEW-04 Core Engineering Standards: đúng, an toàn, rõ, đơn giản, gọn và maintainable, patterns chỉ khi có ích.
5. EEW-05 Domain Standards: chọn security/UI/API/database/performance/integration rules theo task, không ép mọi thứ.
6. EEW-06 Controlled Implementation: permission/scope checks, change manifest, tool effects, Git governance, không ghi đè.
7. EEW-07 Verification: focused → affected regression → risk-specific, evidence gắn code/env; không fake PASS.
8. EEW-08 Review/Convergence: code health + SPEC coverage; không sửa ngoài scope, không trộn changes.
9. EEW-09 DoD/Handoff: task-scoped result, completion != commit/push/deploy, resume từ state+Git.
10. EEW-10 Model/Context/Usage: Core/Active/Relevant/Archive, verified catalog, user switches, local-first metrics.

Các nguyên tắc D04–D10 chi tiết có trong tài liệu lịch sử dưới `docs/`/các bản thiết kế; không tự viết lại thành hàng loạt framework mới.

## 5. SI01–SI14 — PHẠM VI ĐÃ TRIỂN KHAI Ở CANDIDATE

- SI01 Trusted Control Plane — hiện chỉ fail-closed diagnostics, thiếu trusted authority native.
- SI02 Capability Certification — observations + version fingerprints, chưa chứng nhận provider OS/app.
- SI03 State outside working tree — triển khai metadata local, chưa tamper-resistant.
- SI04 Atomic Mutation Protocol — chỉ preflight/hashes, chưa có trusted writer.
- SI05 Task Scoped Git — chỉ scope preview, không stage/commit.
- SI06 Session Fencing — generation/heartbeat observations, chưa enforced OS.
- SI07 Tool Effect Registry — conservative static classification, không cấp permission.
- SI08 Evidence Graph/Freshness — draft dependency/impact, chưa trusted runner.
- SI09 Intent UX — route/preview, natural task/resume, chưa native GUI E2E.
- SI10 Engineering Profile Exceptions — proposal, không tự đổi standards.
- SI11 Durable Recovery — state doctor/backup checks, native reconciliation chưa có.
- SI12 Action-Specific Authorization — kiểm tra yêu cầu quyền riêng, không tự grant.
- SI13 Verification Footprint — test plan/resource conflict previews, chưa isolated execution trên provider.
- SI14 Native Installer Certification — **chỉ** guidance installer và scratch smoke; native sign/cert chưa có.

Người dùng đã yêu cầu tạm bỏ qua EA01–EA16 trong giai đoạn triển khai SI; **không xóa legacy code**, nhưng không mở phạm vi mới theo các nhãn EA nếu chưa có yêu cầu mới.

## 6. HIỆN TRẠNG BỘ KIT BẠN NHẬN

Mở trước tiên `README_START_HERE.md`, `docs/MVP_SCOPE_AND_DECISIONS.md`, `guides/01_HUONG_DAN_TICH_HOP.md`, `guides/02_HUONG_DAN_SU_DUNG.md`, `guides/03_BAO_CAO_GIOI_HAN_VA_NGHIEM_THU.md`, `docs/LAST_SELF_REVIEW_VI.md`, `release/ONE_SHOT_ACCEPTANCE.json` và `release/PRACTICAL_SMOKE.json`. Đây là nguồn trạng thái mới nhất; tài liệu RC.1/SI cũ chỉ dùng làm **historical evidence**.

Các lệnh cốt lõi (chạy trong kit, `--repo` trỏ vào REPO GIẢ trước):

```sh
python3 tools/verify_release.py
python3 tools/agentflow.py --repo "/ABS/REPO" doctor
python3 tools/agentflow.py --repo "/ABS/REPO" install-guidance                  # dry-run
python3 tools/agentflow.py --repo "/ABS/REPO" install-guidance --apply          # STRICT default
python3 tools/agentflow.py --repo "/ABS/REPO" install-guidance --mode advisory --upgrade --apply  # EXPLICIT OPT-IN
python3 tools/agentflow.py --repo "/ABS/REPO" interact "mô tả yêu cầu"
python3 tools/agentflow.py --repo "/ABS/REPO" resume "tên công việc"
python3 tools/agentflow.py --repo "/ABS/REPO" repo-status
python3 tools/agentflow.py --repo "/ABS/REPO" tasks
python3 tools/practical_smoke.py
python3 tools/release_acceptance.py
```

Chức năng hiện có: task intake/lookup, contract template+DoR, profile/domain proposals, Technical Plan/DAG drafts, checkpoint/evidence reports unverified, handoff packet, Git snapshot, final-review, SI diagnostics và installer guidance. Tất cả giải quyết process/observability; **không có native human-approval signer hay mandatory write-broker**. Không tự đồng nhất việc `ADVISORY` cho provider coding với thực hiện strict security.

`STRICT` là mặc định; trong mode này instructions yêu cầu không sửa product code. `ADVISORY` là chế độ **user tự chọn**, cho phép coding qua tool/permissions vốn có của provider sau khi user đồng ý đúng Task Contract trong chat; đó chỉ là process convention, KHÔNG chống được một tiến trình bypass. Không có ứng dụng/UI bổ sung; không cài hooks, sudo, cài daemon hoặc sửa permissions của repo.

## 7. TRẠNG THÁI G0–G7 VÀ GIỚI HẠN

- G0: HISTORICAL LOCAL PASS; G1: LOCAL PASS.
- G2: **BLOCKED — native trusted approval và OS mandatory enforcement chưa có**.
- G3: PARTIAL — task navigation/DoR/contract ở local, chưa E2E provider GUI/CLI.
- G4: PARTIAL — planning/policies/DAG proposal, chưa có trust-activated execution.
- G5: **BLOCKED — code writes qua trusted boundary, atomic shared Git, trusted tests/review chưa có**.
- G6: PARTIAL — handoff/context/model advice, chưa có trusted DoD/completion.
- G7: PARTIAL — installer guidance/backups/rollback thử trên scratch; chưa chứng nhận native trên Mac.
- 317/317 local tests PASS (312 regression + 5 Preview), 9/9 scratch baseline smoke, 20/20 scratch practical E2E. Các số này là **bằng chứng local**, không chứng minh chạy trên macOS hoặc app hãng thứ ba.

**Không tự nói “Đ3–Đ7 hoàn thành production”** vì những thành phần thực thi thật còn thiếu. Báo cáo trung thực như trên dù người dùng mong sớm dùng được.

## 8. NHIỆM VỤ NHẬN BÀN GIAO — LƯỢT ĐẦU CHỈ AUDIT, KHÔNG SCALE

1. **Xác minh gói:** hash manifest, số files, `tools/verify_release.py`, yêu cầu Python, `README`, tests. Đọc code có liên quan thay vì tin hoàn toàn vào report. Không chạy lệnh trên repo sản phẩm khi chưa được user xác nhận.
2. **Tái hiện trong repo giả:** cài dry-run/apply STRICT → xem blocks → thử `ADVISORY` chỉ khi người dùng cho phép → test một Quick task (nếu đang trong môi trường Codex/Claude thật), task lookup/resume, diff/evidence, remove/rollback. Chỉ thao tác trong repo test, không dùng credentials thật.
3. **Đánh giá tính hữu dụng:** Agent có tự đọc AGENTS.md/CLAUDE.md không? Người dùng có phải copy/paste quá nhiều không? Task Contract có gọn không? Một yêu cầu Quick có cần chạy CLI không? Có đoán PASS/DoD không? Có để xót changes người khác không?
4. **Phân loại đúng từng bề mặt:** Codex Desktop, Codex CLI, Claude Desktop Code, Claude Code CLI. Cái nào chưa test thì `NOT_RUN/NOT_CERTIFIED`, không suy từ CLI sang GUI.
5. **Kiểm tra đúng D3–D7:** RIG/DoR/approval, planner/policies, coding workflow với permissions provider, testing/review, resume, installer/rollback. Đánh giá bằng hành vi trong repo giả trước; chỉ mở code khi có lỗi cụ thể.
6. **Kiểm tra security gaps:** hardlink/symlink/traversal, shell/patch/MCP bypass, state tampering, direct write, Git index, preopened FDs, concurrent sessions. Không tự gọi test giả lập là security certification.
7. **Review code health:** duplication, complexity, quá nhiều adapters/flags/files, stale docs, dead code, backwards compatibility, installer ownership và rollback. Ưu tiên **loại bỏ phức tạp** nếu không dùng.
8. **Đối chiếu quyết định:** tách `USER_CHỐT`, `PROPOSAL`, `TESTED`, `BLOCKED`; không tự đưa thêm GUI, daemon, sandbox/UID changes, subagents hay nhiều worktree.

## 9. ĐẦU RA BẮT BUỘC CHO NGƯỜI DÙNG TRƯỚC KHI TỰ TRIỂN KHAI TIẾP

**Báo cáo ngắn, có bằng chứng**, theo bảng:

| Hạng mục | Đã làm/test? | Bằng chứng thực tế | Ảnh hưởng tới coding ngay | Đề xuất nhỏ nhất | Mức ưu tiên |
|---|---|---|---|---|---|
| Repo onboarding | ... | ... | ... | ... | ... |
| RIG/Task Contract | ... | ... | ... | ... | ... |
| Plan/Work Graph | ... | ... | ... | ... | ... |
| Writing/G2 | ... | ... | ... | ... | ... |
| Verification/G5 | ... | ... | ... | ... | ... |
| Resume/Model | ... | ... | ... | ... | ... |
| Installer/G7 | ... | ... | ... | ... | ... |

Phân tách: **P0 blockers cần xử lý trước 1 Quick coding test**, **P1 lỗi cần xử sau khi test hữu dụng**, **P2 backlog hoãn**. Mỗi đề xuất cần test case chứng minh lỗi, diff dự kiến nhỏ và rollback. Nêu cả những yêu cầu không thể chứng minh vì thiếu macOS/native. **Không chạy triển khai lớn khi chưa gửi báo cáo và được user chọn phương án.**

## 10. NGUYÊN TẮC KỶ LUẬT CHO MỌI PHIÊN SAU

- Tránh kiến trúc/platform hóa. **Đầu tiên dùng được trên repo rồi mới tối ưu từ vấn đề thật**.
- Khi gặp security blocker, không giả PASS hoặc tự đổi UX để né. Đề xuất trade-offs rõ ràng và hỏi đúng quyết định thuộc người dùng.
- Giữ tư duy ONE repo, ONE working tree, FOUR interfaces, NO app mới, MINIMUM sufficient process.
- Không chủ động thêm repo khác, worktree, CI/CD, shell privileges, package dependencies, model API calls hoặc cloud telemetry.
- Mọi thay đổi cần source diff nhỏ, test/evidence, trạng thái chính xác; commit/push/deploy là quyền riêng.
- Người dùng yêu cầu tiết kiệm thời gian và usage; **không xây thêm tính năng chỉ vì số mục trong backlog**. Nếu chỉ cần sửa một tệp/điều kiện để coding thuận lợi, làm đúng mức đó sau khi được duyệt.

**Bắt đầu ngay bằng review ZIP và báo cáo khoảng trống/đề xuất; chưa tự thay đổi repo thật hoặc xây sản phẩm mới.**
