# Design Baseline — ĐÃ ĐƯỢC DUYỆT VỀ THIẾT KẾ

## Các quyết định nền tảng

- **RIG:** 8 trách nhiệm trong một Adaptive Preflight Loop, cùng 10 điều chỉnh A01–A10. SPEC versioned, DoR, human approval đúng revision.
- **EEW:** 10 chuyên đề EEW-01..EEW-10 đã được chốt; EEW-04 có D04-01..D04-14; EEW-05 có D05-01..D05-14; EEW-06/07/08 có 32 nguyên tắc; EEW-09/10 có 24 nguyên tắc.
- **EEW Design Audit:** EA-01..EA-16 đã chốt: owner, state, policy version, approval trust, enforcement feasibility, multiwriter, freshness, plan/work graph, domain selection, test isolation, review/DoD, Git, handoff, model/context, telemetry.
- **System Integration Review:** SI-01..SI-14 đã được chốt: Trusted Control Plane; per-provider capability certification; runtime metadata outside repo; atomic mutations/fencing; task-scoped Git operations; session identity/crash recovery; Tool Effect Registry; versioned Evidence Dependency Graph; robust natural Task Navigator; bootstrap/exception policy; durable local state/recovery; distinct sensitive action approvals; resource-aware tests; installer/upgrade/certification.

## Bất biến không được tự hạ mức

1. Một repository + một working tree local macOS; đa task và đa session ghi đồng thời chỉ khi chứng minh an toàn.
2. Không auto-switch Codex↔Claude, không auto-select model; không phụ thuộc subagents.
3. Bạn không cần nhớ Task ID hoặc tự tạo task, file scope hay risk bằng command.
4. RIG đọc an toàn trước approval; thao tác có side effects cần quyền riêng; câu trả lời làm rõ không phải approval.
5. `SPEC_APPROVED` != `SESSION_ACTIVATED` != `WRITE_AUTHORIZED`; approval bảo vệ bởi Trust Boundary chứ không phải mỗi hook.
6. Không tự commit, push, deploy hoặc thay đổi dữ liệu production.
7. Code Simple, Concise & Maintainable; design patterns theo lợi ích thực, đúng idioms/stack/domain.
8. Test PASS chưa đủ; review, convergence và DoD phải có bằng chứng còn hiệu lực.
9. Fail closed nếu Strict Enforcement chưa được chứng minh ở bề mặt đang sử dụng.
10. Chỉ nạp context liên quan và kiểm tra đúng mức rủi ro; không biến 8 RIG + 10 EEW thành 18 lượt model mặc định.

## Trạng thái triển khai tại Đ0

Các thiết kế trên được duyệt **để triển khai**, không đồng nghĩa đã có mã hoặc bằng chứng nghiệm thu. Source Preview đang được giữ nguyên làm nguồn tham chiếu cho migration/refactor. Bản phát hành đầu tiên chỉ được gắn nhãn production-ready sau khi đạt G0..G7 và capability certifications cần thiết.
