# Tiến độ 8 đợt Agent Workflow V3

| Đợt | Trạng thái | Bằng chứng |
|---|---|---|
| Đ0 Development Baseline | G0 PASS | Preview core, installer scratch tests |
| Đ1 Canonical Foundation | G1 PASS | SQLite migrations/state/concurrency/crash/backup tests |
| **Đ2 Trusted Approval & Enforcement** | **PROTOTYPE TESTS PASS; G2 BLOCKED / NOT_CERTIFIED** | Ed25519 receipt verification, single-use challenges, default-deny, tool effects, scratch atomic mutation, read-only capability probe. Chưa chạy chứng nhận macOS native/GUI. |
| Đ3 Task Navigator + RIG | NOT_STARTED | Phụ thuộc Đ2 trusted boundary đối với quyền code |
| Đ4 Engineering Intelligence | NOT_STARTED | Engineering/Domain profiles, integrated planning |
| Đ5 Execution & Quality | NOT_STARTED | Trusted mutation/manifest, test/review/convergence |
| Đ6 Completion & Continuity | NOT_STARTED | Handoff, DoD, model/context/metrics |
| Đ7 Release + Guides | NOT_STARTED | Installer, docs, native capability matrix |

Đ2 không được tự cấp PASS G2. Bộ prototype chỉ dùng cho nghiên cứu và kiểm thử local. Nếu thực tế macOS không hỗ trợ một surface đã định, phải giữ surface `NOT_CERTIFIED` hoặc bổ sung kiến trúc isolation được kiểm nghiệm.
