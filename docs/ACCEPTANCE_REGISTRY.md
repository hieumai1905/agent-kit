> **v1.0 thực dụng, 02/11/2026:** người dùng đã duyệt phạm vi ADVISORY/Codex local/một writer tại ../release/V1_0_SCOPE.md. FINAL/ENFORCED và các gate security trong registry lịch sử này vẫn chưa đạt; không phải điều kiện tuyên bố chứng nhận cho v1.0. Xem ../release/V1_0_ACCEPTANCE.json. Không tự mở rộng backlog.

# Acceptance Registry — Golden Scenarios theo đợt

**Kết quả được phép:** PASS / FAIL / BLOCKED / NOT_RUN. Không có `PASS` nếu không có câu lệnh, evidence, code version, environment, expected/actual và thời điểm.

| Case | Đợt | Expected result |
|---|---|---|
| W0-01 | Đ0 | Mã nguồn Preview/zip được định danh SHA-256, không chỉnh sửa nguyên bản |
| W0-02 | Đ0 | 5 core tests cũ PASS trong môi trường cách ly |
| W0-03 | Đ0 | Installer dry-run không sửa repo thử |
| W0-04 | Đ0 | Installer apply/rollback bảo toàn file gốc trong repo thử |
| W1-01 | Đ1 | Unauthorized transition bị từ chối |
| W1-02 | Đ1 | SPEC/version/policy event nhất quán khi cập nhật song song |
| W1-03 | Đ1 | Crash/migration/backup không đánh mất trạng thái |
| W1-04 | Đ1 | Preapproval state nằm ngoài Git working tree |
| W2-01 | Đ2 | User chưa duyệt -> deny write across claimed tools |
| W2-02 | Đ2 | Revoked/wrong-version approval -> deny write |
| W2-03 | Đ2 | Hook missing/error/bypass attempt -> no unauthorized write on certified surface |
| W2-04 | Đ2 | Symlink/path traversal/TOCTOU attempt bị chặn ở trusted boundary |
| W2-05 | Đ2 | Fencing: old session không được ghi sau lease ownership change |
| W2-06 | Đ2 | Capability certificate theo đúng version macOS + bốn adapter được tuyên bố |
| W3-01 | Đ3 | Task mới vs tiếp tục/sửa/hỏi/duyệt phân loại chính xác trong golden prompts |
| W3-02 | Đ3 | No manual Task ID, duplicate questions, or unintended task creation |
| W3-03 | Đ3 | Clarification answer != task approval |
| W3-04 | Đ3 | Read-only discovery cannot silently modify product files |
| W4-01 | Đ4 | Quick plan ngắn; Deep plan đủ mà không dư tài liệu |
| W4-02 | Đ4 | Work DAG hợp lệ; incremental replanning chỉ invalidates impacted nodes |
| W4-03 | Đ4 | Engineering Profile được duyệt và dùng lại; không máy móc hóa design patterns |
| W4-04 | Đ4 | Domain standards chỉ bật khi liên quan stack/risk/task |
| W5-01 | Đ5 | Two writers conflict same file -> no lost update |
| W5-02 | Đ5 | Two disjoint changes sharing contract -> coordination decision |
| W5-03 | Đ5 | Task-scoped Git staging không lấy thay đổi task khác |
| W5-04 | Đ5 | Concurrent test DB/ports/resource không gây nhiễu lẫn nhau |
| W5-05 | Đ5 | Test PASS bị invalidate khi code/env dependency ảnh hưởng thay đổi |
| W5-06 | Đ5 | Code excessive abstraction bị flag để review; không ép refactor ngoài scope |
| W5-07 | Đ5 | Missing acceptance criterion -> convergence không PASS |
| W6-01 | Đ6 | Unknown usage => UNKNOWN, never guessed; no automatic platform/model switching |
| W6-02 | Đ6 | Crash resume từ persisted state + Git, không cần transcript |
| W6-03 | Đ6 | Task complete != committed/pushed/deployed |
| W6-04 | Đ6 | Local-first sensitive data handling; no implicit telemetry export |
| W7-01 | Đ7 | Fresh install + doctor + backup + upgrade + rollback + uninstall passes |
| W7-02 | Đ7 | Codex GUI/CLI, Claude GUI/CLI E2E tested/certified per claimed version |
| W7-03 | Đ7 | Natural task → approval → implementation → test → review → DoD passes |
| W7-04 | Đ7 | Setup Guide reproduces fresh installation on macOS test repo |
| W7-05 | Đ7 | User Guide reproduces resume, handoff, conflicts and fail-closed UX |
| W7-06 | Đ7 | Final release manifest/checksums and known limitations accurately match capabilities |

## Critical release blocks

G2 (Trusted Approval/Enforcement), G5 (atomic concurrency + verification), G7 (four claimed adapters + docs) là cổng bắt buộc cho phát hành FINAL. Nếu bề mặt nào chưa được chứng nhận, nó phải được tách khỏi mọi tuyên bố `ENFORCED`; chỉ phát hành giới hạn nếu người dùng chấp thuận rõ sự thay đổi mục tiêu/phạm vi.

## Đ1 — Tăng cường bằng chứng G1 (đã chạy trên repo tạm)

| Case | Trạng thái/kịch bản đã mã hóa | Test/source |
|---|---|---|
| W1-01 | Task/work/session illegal state transitions và self-approval bị từ chối | `test_invalid_task_transition_rejected`, `test_approval_cannot_be_self_issued_in_d1` |
| W1-02 | Concurrent CAS + idempotency + schema init trong nhiều tiến trình | `test_parallel_process_optimistic_updates_no_lost_write`, `test_concurrent_idempotent_call_one_result`, `test_parallel_process_initialization_is_atomic` |
| W1-03 | Atomic migration, forced process death, backup, checksum, restore chỉ vào vùng mới | `test_forced_process_crash_rolls_back_partial_write`, `test_migration_v1_to_v2_preserves_rows`, `test_consistent_backup_and_fresh_restore` |
| W1-04 | Repo product file không đổi; trạng thái runtime nằm bên ngoài working tree | `test_database_healthy_and_outside_working_tree`, `test_state_home_inside_repo_is_rejected` |
| W1-05 | Immutable policy/contract/evidence và audit integrity | `test_contract_policy_and_evidence_records_are_immutable`, `test_audit_is_append_only_and_valid` |
| W1-06 | Evidence hết hiệu lực khi artifact liên quan thay đổi; PASS không được chứng nhận | `test_artifact_dependency_invalidates_evidence` |
| W1-07 | Intent hết TTL không tự giải phóng/cấp quyền ghi, generation không bị reuse | `test_resource_intents_do_not_authorize_writes`, `test_expired_intent_is_not_silently_stolen` |
| W1-08 | Không tự nhập DB Preview/unversioned, không nâng cấp migration history giả | `test_unknown_unversioned_preview_db_refused`, `test_migration_history_mismatch_fails_closed` |

**Bằng chứng thực thi:** `.release/WAVE1_ACCEPTANCE.json` ghi số test, lệnh, platform, timestamp, source checksums và kết quả G1. `G1 PASS` không chứng nhận an toàn GUI / write enforcement; các thử nghiệm đó thuộc G2/G5/G7.
