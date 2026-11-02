# BÁO CÁO BÀN GIAO — AGENT WORKFLOW SYSTEM V3.0 RC.1

**Bản tích hợp:** Release Candidate RC.1  
**Ngày:** 29/10/2026  
**Kết luận:** **Đã xây và kiểm thử local được phần read-only/draft và tài liệu; chưa thể bàn giao bộ tích hợp security-enforced hoạt động đầy đủ trên Codex/Claude macOS.**

## I. Những việc đã thực hiện trong đợt tổng hợp

1. Kế thừa phần mã Đ0–Đ2.1 và kiểm thử regression.
2. Schema v4 mở rộng Canonical State bằng hồ sơ workflow có phiên bản, alias và adapter observations; chuyển đổi từ schema v3 lên v4 giữ nguyên dữ liệu.
3. D3: natural-language task navigation, preflight bounded repo discovery và RIG brief ở trạng thái chưa đủ duyệt, context/assumption warning.
4. D4: engineering profile đề xuất theo repo, domain resolver, technical plan gắn contract hash, DAG validation và candidate scheduling chưa có quyền ghi.
5. D5: nối tool-effect classifier và unverified evidence/review. Không phát lệnh mutation, không cấp `REVIEW_PASS` hay DoD.
6. D6: handoff packet từ hồ sơ task, model advisor theo catalog người dùng, usage không có nguồn là UNKNOWN, không chuyển model tự động.
7. D7: guidance-only installer có dry-run/backup/remove, command-line toolkit, manifest SHA-256, kiểm thử một lượt và tài liệu cài đặt/sử dụng bằng Markdown + PDF.
8. Củng cố tests nhiều session về optimistic revision/SQL và khả năng từ chối self-approval.

## II. Kết quả kiểm thử

Đã chạy `python3 tools/release_acceptance.py` với cả suite thử nghiệm hiện có, legacy Preview smoke và scratch repository intake. Kết quả mới nhất lưu tại `release/ONE_SHOT_ACCEPTANCE.json`, gồm tổng số bài, chi tiết và trạng thái. Một kết quả PASS ở đây chỉ khẳng định những API và nhánh được kiểm tra trong môi trường local.

## III. Trạng thái nghiệm thu tám đợt

| Gate | Kết quả |
|---|---|
| G0 | PASS baseline đã có từ trước |
| G1 | PASS local schema/state regression (v4) |
| G2 | **BLOCKED**: không có native trusted human approval + OS mandatory write boundary |
| G3 | PARTIAL: task navigation/draft, chưa có GUI agent semantic integration đã chứng nhận |
| G4 | PARTIAL: plan/profile/work graph proposal, chưa activate policy đáng tin |
| G5 | **BLOCKED**: không có sản phẩm code write/verification với quyền cưỡng chế |
| G6 | PARTIAL: handoff/model advisor; không có trusted completion loop |
| G7 | PARTIAL: bundle+guide+installer read-only, chưa có native signed integration certification |

## IV. Vì sao không tuyên bố hoàn thành toàn bộ?

Một tiến trình agent chạy cùng macOS user có thể ghi trực tiếp vào những file mà user đó có quyền, qua shell/editor/MCP; một database và chữ ký được giữ trong vùng agent có thể sửa không đủ bảo vệ approval. Đ2.1 đã tái hiện alias hardlink ngoài sandbox khiến canary thay đổi. Chỉ khi ứng dụng agent không có đường direct write vượt qua broker, cơ chế cấp quyền và write leases mới thực sự cưỡng chế được. Ở container này không có macOS GUI thật, danh tính ký code, quyền admin hay khả năng test các đường ghi của ứng dụng bên thứ ba.

Không nên cài hooks rồi gọi G2 PASS. Tất cả adapters giữ `NOT_CERTIFIED`. Không dùng RC.1 làm lớp an toàn duy nhất cho repo sản phẩm.

## V. Những công việc thực sự còn lại trước khi có bộ hoàn chỉnh

**Blocker A — Mac Control Plane/Approval:** xây UI người dùng riêng + trust realm/signing key + revocation + audit được bảo vệ khỏi agent, build & code-sign.

**Blocker B — Mandatory Write:** OS sandbox/identity isolation có hiệu lực với 4 bề mặt, protected helper/write broker, chống direct write, preopened FDs, hardlink/symlink/rename, Git/test resources.

**Blocker C — Provider Integration:** chứng minh adapters có thể thao tác tự nhiên trong Codex/Claude đúng build mà không cần user nhập task ID, đồng thời không bật writer khi certification chưa đạt.

**Blocker D — True Execution/Quality:** lập trình EEW-06 đến EEW-09 có trusted code mutation, verification runner/evidence, review/DoD bound vào code version, task-scoped Git operations, crash recovery.

**Blocker E — macOS Certified Installer:** installer native helper, doctor/upgrade/uninstall/rollback có ký, compatibility matrix và một lượt native acceptance sau cùng trên repo giả.

## VI. Những gì người dùng cần làm

**Ngay bây giờ: Không cần chạy thêm phép thử lẻ.** Các kết quả inventory và hardlink lab trước đó đã đủ để chỉ ra vấn đề.

**Để đạt phát hành cuối:** cần quyền xác nhận/đăng ký helper macOS, setup security realm trong một buổi kiểm thử native tổng hợp trên repo giả. Chỉ đề nghị khi gói native thật sự sẵn sàng, có rollback, test matrix và kết quả các negative tests trong build. Không yêu cầu người dùng giao private keys hay sửa repo thật qua chat.

## VII. Sản phẩm đính kèm

- Mã nguồn RC.1 và tests trong ZIP, gồm toàn bộ các phần trước đó.
- `guides/01_HUONG_DAN_TICH_HOP.md` và PDF tương ứng.
- `guides/02_HUONG_DAN_SU_DUNG.md` và PDF tương ứng.
- `guides/03_BAO_CAO_GIOI_HAN_VA_NGHIEM_THU.md` và PDF tương ứng.
- `release/ONE_SHOT_ACCEPTANCE.json`, `release/CAPABILITIES.json`, `release/MANIFEST_SHA256.json`.

**Không được đổi trạng thái G2/G5/G7 thành PASS chỉ vì tài liệu và tests local đã hoàn thành.**
