> **Mốc hiện hành v1.0 — 02/11/2026:** Báo cáo lịch sử ngày 29/10; số test/backlog và NOT_RUN ở dưới thuộc mốc đó. Bản giao hiện hành: ../release/V1_0_ACCEPTANCE.json. Không tự triển khai backlog.

# BÁO CÁO TÍCH HỢP Đ3–Đ7 / REVIEW CUỐI

**Bản:** 3.0-practical-integration.1 · **29/10/2026**  
**Loại phát hành:** NON_CERTIFIED_PRACTICAL_INTEGRATION_CANDIDATE  
**Kết luận:** Đã có kit hướng dẫn cài vào repo và công cụ task/contract/plan/handoff/review ở mức local; chưa có chứng nhận strict enforcement/macOS GUI/CLI.

## 1. Những gì thực sự đã triển khai trong lượt này

- Bắt đầu từ **SI01–SI14 Development Candidate** đã có 297 bài regression (trong đó 63 bài SI) và 5 Preview.
- Không phát triển thêm EA01–EA16; không thêm GUI, SwiftUI, daemon, network backend, tự chuyển model hoặc hệ thống agent mới.
- **Đ3:** Luồng onboarding hướng dẫn agent, natural-language task intake, task lookup/resume bằng tên, contract readiness; không tự xác minh semantic approval.
- **Đ4:** Profile đề xuất, Technical Plan/DAG draft có kiểm tra, không kích hoạt policy ngoài hợp đồng.
- **Đ5:** Git snapshot read-only, hướng dẫn phối hợp diff/Git, review đúng scope, phân tách test reports là unverified; **không có trusted writer, test runner cho repo sản phẩm hoặc multiwriter hard enforcement**.
- **Đ6:** Handoff compact + live Git snapshot, review cuối hiển thị evidence thiếu, model advisor và usage UNKNOWN nếu không có nguồn.
- **Đ7:** Installer cho `AGENTS.md`/`CLAUDE.md` có dry-run, STRICT default, ADVISORY opt-in, nâng cấp explicit, backup + rollback có hash, uninstall; smoke E2E trên repo tạm.
- Đã thêm 15 tests regression thực dụng (`tests/test_practical_workflow.py`) và `tools/practical_smoke.py` (20 bước). Giao thức SI gốc vẫn có trong `agentflow_si`.

## 2. Bằng chứng kiểm thử

| Hạng mục | Kết quả đã quan sát | Giới hạn |
|---|---|---|
| Regression SI + D0–D7 | **312/312 PASS** trên host Linux | Tests local, không mô phỏng trung thực mọi provider |
| Legacy Preview | **5/5 PASS** | Smoke của preview, không chứng nhận native |
| Tổng automated unittest | **317/317 PASS** | Không cấp security PASS |
| Scratch smoke cũ | **9/9 PASS** | Không sửa mã nguồn repo tạm |
| Practical scratch E2E mới | **20/20 PASS** | Cài vào repo giả, task→contract/plan→handoff/review→rollback |
| Actual Codex/Claude Desktop/CLI | **NOT_RUN** | Chưa có máy Mac/app của người dùng trong môi trường kiểm thử |
| Hard enforcement G2 | **BLOCKED** | Không có native trusted approval/write boundary |

Một lần chạy runner tổng hợp có độ trễ/timeout bất thường; kết quả acceptance đã được ghi sau lượt chạy thành công. Theo dõi ổn định subprocess runner trên môi trường khác; không dùng một báo cáo PASS local để suy đoán production. File bằng chứng: `release/ONE_SHOT_ACCEPTANCE.json`, `release/PRACTICAL_SMOKE.json` và hash manifest.

## 3. Trạng thái gate trung thực

| Gate | Trạng thái | Ý nghĩa |
|---|---|---|
| G0 | HISTORICAL LOCAL PASS | Nguồn/gói baseline đã được kiểm tra trước |
| G1 | LOCAL PASS | Schema/state/concurrency metadata tests đạt |
| G2 | **BLOCKED** | Chưa chứng minh trusted human approval + mandatory OS write denial |
| G3 | **PARTIAL** | RIG/task lookup/contract local sẵn có, chưa chạy end-to-end GUI |
| G4 | **PARTIAL** | Draft planning/profile/DAG chạy local; chưa có execution được bảo vệ |
| G5 | **BLOCKED** | Không có trusted product code mutation/verified testing/review pipeline |
| G6 | **PARTIAL** | Handoff/review/advice local; chưa có trusted completion/DoD |
| G7 | **PARTIAL** | Hướng dẫn cài/revert trên repo giả chạy được; native/macOS chưa chứng nhận |

Đ3–Đ7 đã **được bổ sung để dùng thử quy trình tại repo ngay**, không phải đã nghiệm thu toàn bộ product security specification. Nếu xem đây là “full implementation sản xuất”, đó sẽ là mô tả sai.

## 4. Chế độ sử dụng và những gì không đảm bảo

- `STRICT`: read-only/draft, không được dùng kit để mở khóa ghi source. An toàn hơn cho preflight trong khi G2 bị chặn.
- `ADVISORY`: coding **dưới tool permissions hiện có của Codex/Claude** sau quyết định trong chat, do người dùng **chủ động lựa chọn**. Đây là soft process, **không phải** cơ chế ngăn bypass; không bảo vệ chắc chắn khỏi agent cùng UID cố tình ghi trực tiếp hoặc tự giả approval.
- Không có native helper/certification; SQLite ở cùng user không phải protected authority; app/CLI update có thể thay đổi behavior.
- Chưa có kiểm chứng nhà cung cấp đọc AGENTS.md/CLAUDE.md đúng như dự kiến trên cả bốn bề mặt thực tế.
- Git status là snapshot, không khóa tài nguyên; không tự stage/commit; không đo quota live hoặc cam kết mức tăng hiệu suất.

## 5. Review cuối (theo bằng chứng, không tự tô hồng)

**Đạt ở mức local:** không có UI khác; installer chỉ hai managed instruction files, dry-run mặc định, bảo toàn phần nội dung riêng, rollback/upgrade explicit, hardlink/symlink checks, task lookup không đoán khi mơ hồ, resume có Git snapshot, review không giả `PASS`, E2E scratch vẫn giữ fixture mã nguồn không thay đổi.

**Điểm cần kiểm tiếp sớm nhất trên Mac:** (i) Codex Desktop/CLI và Claude Desktop/CLI đọc instructions thật; (ii) một Quick coding task trên repo giả với `ADVISORY` đã được chủ động chọn, đối chiếu diff và tool prompts; (iii) test handoff một task giữa provider, phát hiện task trùng; (iv) fail-safe khi có thay đổi Git khác task; (v) installer upgrade/rollback trong repo giả thực tế. Chỉ sau đó tính tới việc bổ sung code khác.

**Không cần xây rộng hơn trước test:** không thêm control-plane app, dashboard, model orchestrator, native daemon, plugin/cloud hay framework nặng nếu chưa có bằng chứng cần thiết và bạn chưa quyết định. Các blocker G2/G5 phải được trình riêng; không được âm thầm downgrade Strict Approval thành ADVISORY.

## 6. Danh sách tồn đọng cần agent tiếp nhận rà soát và đề xuất

1. **P0 / Tích hợp thực:** Xác minh `AGENTS.md` và `CLAUDE.md` được đọc đúng trong bốn công cụ trên đúng bản macOS; ghi các khác biệt API/GUI.
2. **P0 / Thử coding có giới hạn:** Một task sửa nhỏ trong repo giả, mode ADVISORY nếu người dùng chấp thuận riêng; đối chiếu Task Contract, test, diff và chuyển phiên.
3. **P0 / Điều kiện Strict:** Đánh giá phương án chứng thực approval trong chat và ranh giới ghi thật không UI mới; nếu không khả thi cần báo `BLOCKED`, không tự bổ sung app.
4. **P1 / Trạng thái/Git:** Thử multi-session real; đọc các thay đổi không nhận diện, test resource conflicts, crash/recovery. Không đưa multiwriter vào production khi chưa kiểm chứng.
5. **P1 / Test runner stability:** Lặp acceptance trên macOS và xác định nguyên nhân lượt subprocess chậm bất thường.
6. **P1 / Code health:** Kiểm tra yêu cầu Python, path di chuyển kit, quyền và backup trên APFS; sửa theo mức tối thiểu được chứng minh.
7. **P2 / Native enforcement:** Chỉ trình phương án nhỏ nhất với phương án thay thế/đánh đổi trước khi triển khai; giữ nguyên UX bốn công cụ.

## 7. Tiêu chí tiếp tục

Chỉ mở rộng khi có lỗi thực tế hoặc acceptance case mới chưa qua. Mỗi đề xuất cần: vấn đề đã thấy, bằng chứng, tác động người dùng, thay đổi tối thiểu, 1–3 test case và rollback. Giữ toàn bộ backlog khác ở trạng thái DEFERRED. Mục tiêu là **sớm dùng được để coding**, ít friction và không phát triển một sản phẩm mới.
