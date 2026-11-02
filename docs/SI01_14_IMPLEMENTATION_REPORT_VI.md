# BÁO CÁO TRIỂN KHAI SI01–SI14 — AGENT WORKFLOW SYSTEM V3.0

**Ngày:** 29/10/2026  
**Candidate:** `3.0-si-candidate.1` (kế thừa RC.1)  
**Phạm vi:** Chỉ SI01–SI14. EA01–EA16 **không nằm trong đợt sửa đổi này**; các chức năng cũ được giữ nguyên để không phá backward compatibility.  
**Lớp phát hành:** `NON_CERTIFIED_SI_DEVELOPMENT_CANDIDATE` — chỉ inspect/plan/draft, không sửa product code.  
**Trải nghiệm:** Giữ nguyên Codex Desktop, Claude Desktop (Code), Codex CLI, Claude Code CLI. **Không phát triển UI/app riêng.**

## 1. Tóm tắt điều hành

**Đã làm:** triển khai `agentflow_si` với ba module `foundations.py`, `operations.py`, `workflow.py`; kết nối các công cụ SI vào `tools/agentflow.py`; mở rộng loại workflow draft; thêm 63 unit/regression tests SI, bổ sung 3 scratch-smoke steps, xây SI-only acceptance runner và release report. Không tạo trusted signing key, không sửa cấu hình hoặc chạy provider, không sửa repo sản phẩm.

**Kết quả kiểm thử:** `python3 tools/release_acceptance.py`: 297/297 regression PASS (bao gồm 63 test SI mới), 5/5 Preview PASS, **302/302 PASS**; scratch smoke 9/9 PASS. `python3 tools/si_acceptance.py`: 63/63 SI tests PASS; đủ 14 ID được covered; 5/5 SI CLI smoke PASS; sentinel repository không đổi. Host: Linux x86_64, Python 3.13.5. **Local PASS không xác minh bảo vệ macOS.**

**Còn thiếu:** Không có trusted human approval authority nằm ngoài quyền của agent; không có macOS enforced write broker/OS isolation; chưa kiểm thử các đường ghi thực của 4 adapter; Git mutation/verification side effects vẫn bị chặn; native installer và upgrade certification chưa có. **G2=BLOCKED, G5=BLOCKED, G7=PARTIAL.**

## 2. Ma trận triển khai SI01–SI14

| SI | Thành phần đã triển khai và test được | Cấp độ hiện tại | Điều còn thiếu để hoàn thành mục tiêu SI |
|---|---|---|---|
| **SI01 Trusted Control Plane** | `trust_boundary()` trả quyết định deny, phân biệt chat approval/SQLite cùng UID với quyền thật; không phát approval/grant | **BLOCKED_NATIVE_TRUST** | Một nguồn xác thực phê duyệt qua môi trường người dùng hiện tại, authority/ledger tách quyền agent, OS attestation; không tự ép thêm UI |
| **SI02 Provider Capability Certification** | Ma trận 4 surfaces, fingerprint observation dựa trên app/build/OS/config/tool paths; từ chối dữ liệu sai | **LOCAL_OBSERVATION_ONLY** | Native capability tests cho từng app+build+OS+mode+tool path; chưa có certificate |
| **SI03 Runtime Metadata Outside Working Tree** | Dùng `StateStore` bên ngoài repo, kiểm tra export destination, chỉ tạo kế hoạch export không động vào file | **LOCAL_IMPLEMENTED_RESTRICTED** | Export có quyền đáng tin và redaction/retention chính thức nếu sản phẩm đòi |
| **SI04 Atomic Mutation Protocol** | `mutation_preflight()` kiểm tra relative path, traversal, symlink, hardlink, casefold alias, before SHA256, claimed fence; **không apply** | **PRECHECK_ONLY** | Trusted atomic broker có recheck/fence và OS deny direct write, journal/rollback; native adversarial tests |
| **SI05 Task-Scoped Git** | `git_scope_preview()` đối chiếu changed/staged/foreign paths qua `git status` với optional locks off; không stage/commit/push | **DRY_RUN_ONLY** | Task-scoped Git transaction thực có quyền riêng, kiểm thử shared index/HEAD trên macOS |
| **SI06 Session Identity/Crash Fencing** | Quan sát session namespace, revision, resource generations, TTL, heartbeat cũ, reconciliation flags; không cấp lease thực thi | **COOPERATIVE_DIAGNOSTICS** | Crash-safe privileged fencing có xác thực session/app identity và kiểm chứng multiwriter native |
| **SI07 Tool Effect Registry** | `classify_effect()` bảo thủ với shell/child/dynamic commands, tách observed effect và khai báo tự nhận, luôn không cấp quyền | **CONSERVATIVE_DIAGNOSTICS** | Verified per-tool effects và containment của subprocess/MCP/test/network trên đúng provider |
| **SI08 Versioned Evidence Dependency Graph** | DAG kiểm cycle/missing/duplicate, propagation invalidation có chọn lọc, snapshot hash và lưu versioned untrusted draft ngoài repo | **LOCAL_DRAFT_ONLY** | Gắn với trusted code/env/test events và provenance của reviewer/DoD thật |
| **SI09 Intent Routing/UX** | `intent_preview()` dùng router + Task Navigator hiện có, ngăn approval claim tạo quyền, không tạo task khi hỏi, disambiguation mà không bắt nhập ID | **LOCAL_PREVIEW_ONLY** | Adapter events đã được xác minh trong Codex/Claude GUI/CLI; test hội thoại E2E thật |
| **SI10 Engineering Bootstrap/Exceptions** | Đề xuất policy exception đủ owner/reason/scope/expiry, validate TTL, lưu `SI_POLICY_EXCEPTION` bằng revision, không activate | **LOCAL_DRAFT_ONLY** | Repo-profile approval theo nguồn người dùng đáng tin, policy activation/exception revocation |
| **SI11 Durable State/Recovery** | Dùng SQLite v4 hiện có, kiểm doctor, audit chain, backup SHA256, cảnh báo filesystem-DB không atomic và yêu cầu reconciliation | **LOCAL_RECOVERY_DIAGNOSTICS** | Native recovery journal liên kết trusted apply, crash-injection & rollback thực, audit chống same-UID tamper |
| **SI12 Risk-Scoped Action Approval** | Bảng scope riêng cho read, test, patch, Git stage/commit/push, deploy, migration, policy; lời tự nhận task approved không cho quyền | **LOCAL_RULES_ONLY** | Actual action-grant issuer/checker từ authority đáng tin |
| **SI13 Verification Footprint & Reuse** | Plan test theo code/env hash, xác định shared db/port resources và collisions; claimed PASS/attestation không tránh rerun | **LOCAL_PLANNING_ONLY** | Trusted runner, isolation của tests, evidence nguồn đáng tin và proof of resource locks |
| **SI14 Installation/Upgrade Certification** | Read-only release doctor + guidance installer inspection, per-provider uncertified matrix, fail-closed G2/G5/G7 | **GUIDANCE_ONLY** | Native installer/doctor/upgrade/rollback/uninstall/E2E có chứng nhận macOS |

**Chú ý:** “Đã triển khai” chỉ được hiểu trong phạm vi các API và kiểm thử nêu trên. Không có SI nào được gọi là đạt chứng nhận bảo mật native nếu thiếu bằng chứng của macOS và bốn ứng dụng.

## 3. Các bất biến đã kiểm tra

1. Không thêm UI/app khác; Codex/Claude Desktop và terminal tiếp tục là giao diện người dùng.
2. Không thêm hoặc sửa hook, daemon, OS security policy, shell profile hoặc Git config trong repo người dùng.
3. Trạng thái `UNTRUSTED_DRAFT`/`OBSERVED` không đổi thành approval/DoD/certification.
4. Lời nhắn “Duyệt” không cấp quyền; input có `approved=true`, `build=certified` hoặc `attestation=VERIFIED_BY_TRUSTED_RUNNER` không nâng capability.
5. Mutation preflight không ghi file; Git scope preview không stage, commit hoặc push; test footprint planner không thực thi tests.
6. Chỉ `--save` rõ ràng mới ghi **draft** vào canonical external SQLite; không viết source của repo mục tiêu.
7. Các vấn đề symlink, hardlink, stale hashes, case ambiguity, graph cycles, expiry và resource collisions có unit tests âm tính.
8. Tất cả capability native vẫn `NOT_CERTIFIED` bất kể flags, bản ghi observation hay test local.

## 4. Vị trí mã nguồn mới/sửa đổi

- `agentflow_si/foundations.py`: SI01, SI02, SI03, SI06, SI11, SI14.
- `agentflow_si/operations.py`: SI04, SI05, SI07, SI12.
- `agentflow_si/workflow.py`: SI08, SI09, SI10, SI13.
- `agentflow_runtime/cli.py`: các lệnh developer/internal `si-*` trong CLI hiện có (không bắt người dùng thao tác để dùng workflow hàng ngày).
- `agentflow_runtime/records.py`: đăng ký các loại bản ghi SI phiên bản hóa nhưng không đáng tin (`UNTRUSTED_DRAFT`).
- `tests/test_si_integration.py`: 63 tests local.
- `tools/si_acceptance.py`: runner SI riêng; `tools/release_acceptance.py`: regression+scratch smoke tổng hợp.
- `release/SI14_LOCAL_ACCEPTANCE.json`, `release/ONE_SHOT_ACCEPTANCE.json`: bằng chứng kiểm thử local.

## 5. Các lệnh kiểm tra phát triển (không cần chạy trong repo thật)

Trong một repo *giả* trên Mac hoặc máy phát triển, từ thư mục đã giải nén kit:

```sh
python3 tools/agentflow.py --repo /tmp/agentflow-scratch si-trust
python3 tools/agentflow.py --repo /tmp/agentflow-scratch si-capabilities
python3 tools/agentflow.py --repo /tmp/agentflow-scratch si-release-doctor
python3 tools/agentflow.py --repo /tmp/agentflow-scratch si-action GIT_PUSH
python3 tools/si_acceptance.py
python3 tools/release_acceptance.py
```

Các lệnh kiểm tra trên không có cơ chế cấp quyền thực thi source code. Những `si-*` còn lại đọc JSON proposals, xem `--help` của CLI để biết định dạng; agent có thể gọi nội bộ, không yêu cầu người dùng nhập task IDs thủ công.

## 6. Backlog còn mở trước native testing

**Mức P0:**

- [ ] SI01: chứng minh được nguồn phê duyệt người dùng từ kênh tích hợp hiện tại (không mặc nhiên thêm UI) và authority/protected audit không agent-writable.
- [ ] SI02: xây chứng nhận capability đúng 4 bề mặt, pin OS/app/build/config; kiểm tra bypass tools.
- [ ] SI04: broker/OS boundary thực có compare-and-apply, hardlink+FD+rename tests và recovery; dùng trên repo giả.
- [ ] SI05/SI06: trusted resource fencing, session crash takeover và Git task-scoped mutations.
- [ ] SI12: issuer/grants riêng theo action được G2 bảo vệ.
- [ ] SI14: native installer/doctor/upgrade/rollback và một lượt macOS acceptance.

**Mức P1:**

- [ ] SI03/SI10: export/policy exception activation theo authority; test trình tự approve/revoke.
- [ ] SI07/SI13: proof side effects/test isolation dưới các adapter, trusted runner.
- [ ] SI08/SI09/SI11: nối dependency graph, resume, native provider events và filesystem recovery vào các hoạt động thật.

Tất cả việc native phụ thuộc vào test macOS thực tế. Hiện tại không được tự xem phần BLOCKED thành PASS hoặc thay đổi mô hình giao diện đã chốt.

## 7. Nghiệm thu và điều kiện chuyển giai đoạn

**G0:** historical local baseline, **G1:** local PASS; **G2:** BLOCKED, **G3/G4/G6:** PARTIAL, **G5:** BLOCKED, **G7:** PARTIAL. Kết quả này không thay đổi vì SI candidate.

Tiêu chí vào *native certification batch* là có môi trường Mac test giả, xác nhận app/config, cơ chế native trusted approval và mandatory boundary thực thi, rollback, negative tests, cùng artifact evidence đầy đủ. Chỉ sau đó mới có thể kết luận G2/G5/G7 theo từng bề mặt.

**Không yêu cầu người dùng chạy script lẻ, cấp admin, sửa repo sản phẩm hoặc cung cấp khóa bí mật ở thời điểm hiện tại.**
