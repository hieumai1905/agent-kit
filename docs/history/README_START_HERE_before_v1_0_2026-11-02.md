# AGENT WORKFLOW V3 — BỘ KIT TÍCH HỢP TỐI GIẢN CHO REPO

**Bản:** `3.0-practical-integration.2` · **Ngày:** 30/10/2026  
**Phạm vi:** D3–D7 ở mức tích hợp thực dụng, giữ nền SI01–SI14 từ candidate trước. Tạm không triển khai thêm EA01–EA16.  
**Trạng thái bảo mật:** `NON_CERTIFIED_PRACTICAL_INTEGRATION_CANDIDATE`; G2/G5 vẫn **BLOCKED** đối với hard enforcement, G7 **PARTIAL** đối với macOS native.

**Bản làm việc A1 — 02/11/2026:** thêm protocol delegated ADVISORY opt-in cho Codex cùng host local, template/digest và chẩn đoán bản ghi UNVERIFIED. Default/direct/STRICT giữ nguyên. Xem `guides/06_DELEGATED_ADVISORY.md` và `release/A1_ACCEPTANCE.json` cho kết quả local; chưa cài protocol mới vào Concat hoặc chạy pilot live. `.2` là baseline release; A1 là revision làm việc riêng, ZIP 30/10 không được thay thế.

**Bổ sung A2 — 02/11/2026:** `task-status` và `status_view` dùng chung trong handoff/resume/review/final-review, tách tiến độ được báo, nguồn quyết định, freshness file/contract và canonical lifecycle. Không tự cấp approval/completion hoặc chạy test. Xem `guides/07_STATUS_PRESENTATION.md` và `release/A2_ACCEPTANCE.json`; working revision hiện hành `A1+A2-2026-11-02`.

**Bổ sung A3 — 02/11/2026:** checkpoint theo mốc, template + CAS validation, resume_brief và handoff cho đường `interact` RESUME. Resume không khởi tạo state hoặc tự chọn task mơ hồ. Xem `guides/08_CONTINUITY.md` và `release/A3_ACCEPTANCE.json`; working revision hiện hành `A1+A2+A3-2026-11-02`. Guidance mới chưa cài vào Concat; báo cáo A1/A2 giữ như bằng chứng của các mốc trước.

**Pilot A4 lần đầu — 02/11/2026: CODE PASS, WORKFLOW FAIL, giữ nguyên lịch sử.** Guidance A1–A3 đã được nâng cấp có backup trên Concat. Agent thêm test đúng scope và kiểm thử qua, nhưng vẫn gọi patch sau khi freshness guard trả exit 1, trước checkpoint quyết định. Tại mốc đó chưa triển khai sửa lỗi này. Xem `release/A4_ACCEPTANCE.json`. Phiên CLI mới đã đọc đúng checkpoint PAUSED và giữ nguyên sự cố; kết quả local A1–A3 không thay thế bằng chứng live này.

**Bản sửa guard A4 — 02/11/2026:** thêm checkedPatchFlow và prepare-write/check-write, kiểm save/read-back checkpoint trước callback patch; xem `guides/09_CHECKED_PATCH_FLOW.md`. Đây là luồng tuần tự trên tools provider sẵn có, không là OS broker/grant. Kết quả A4 đầu vẫn giữ nguyên FAIL; nghiệm thu retry phải đọc riêng `release/A4_RETRY_ACCEPTANCE.json`. Working revision `A4-GUARD-REPAIR-2026-11-02`.

**Retry A4 — 02/11/2026: PASS trong phạm vi pilot, có erratum metadata.** Đã có H mới và D r2, một executor trên Concat. Ca stale 75,7 giây dừng trước patch, không đổi 1.262 file hoặc revision trong ca âm. Flow hợp lệ mới lưu/read-back decision rev3 rồi recheck trước patch; chỉ thêm một method tám subcases. Nghiệm thu độc lập: 4/4 tests PASS, ba method cũ nguyên byte, phát hiện ba mutation, HEAD/index/staged diff và mọi file khác nguyên baseline. Phiên CLI mới chỉ đọc tự tìm đúng task và handoff rev5, không ghi repo/state. Field latest message ID trỏ nhầm commentary cũ đã được đính chính riêng; transcript gốc xác nhận refresh chứa commentary mới. Local suite 433 PASS, 1 skip. Đây chưa là chứng nhận G2/G5 hoặc mọi đường gọi tool. Các dòng A1–A3 ở trên mô tả trạng thái tại từng mốc; trạng thái cài/pilot hiện hành nằm ở `release/A4_RETRY_ACCEPTANCE.json`. ZIP baseline 30/10 không bị thay thế.

**Cập nhật pilot:** đã sửa các lỗi installer, state-home, readiness, handoff và SQLite first-use được phát hiện trong audit. Xem `release/PILOT_READINESS.md` và `guides/05_CONCAT_PILOT.md` trước khi bắt đầu thử nghiệm. Các PDF, handoff và báo cáo ngày 29/10 là lịch sử của bản `.1`; kết quả hiện hành nằm ở `release/ONE_SHOT_ACCEPTANCE.json` và hồ sơ retry mới. Guidance đã cài trên Concat; bằng chứng phiên Codex mới chỉ áp dụng cho pilot được mô tả, chưa chứng nhận chung các provider.

## 1. Bộ kit này là gì?

Đây **không phải** phần mềm/nền tảng mới, app, GUI, daemon, model, subagent hay bộ automation thay thế Codex/Claude. Đây là một lớp **hướng dẫn, state phụ trợ và kiểm tra read-only** để làm việc ngay trong:

- Codex Desktop và Codex CLI;
- Claude Desktop (tab Code) và Claude Code CLI;
- Cùng một local repository, một working tree, nhiều task/session; người dùng đổi provider/model thủ công.

Ngày thường bạn chỉ giao việc **bằng ngôn ngữ tự nhiên trong ứng dụng đang dùng**. Agent đọc `AGENTS.md`/`CLAUDE.md`, khảo sát, đề xuất Task Contract ngắn, chờ quyết định, coding có kiểm soát theo chế độ đã chọn, test/review, bàn giao. Công cụ Python chỉ hỗ trợ state, resume, plan, chẩn đoán, không cần người dùng tự nhập Task ID.

## 2. Cài vào repository (không cần sudo, không thay settings của agent)

Giải nén ZIP vào một nơi **bền vững, BÊN NGOÀI repository**. Mở Terminal trong thư mục kit rồi thay `/duong/dan/repo` bằng repo của bạn:

```sh
python3 tools/agentflow.py --repo "/duong/dan/repo" doctor
python3 tools/agentflow.py --repo "/duong/dan/repo" install-guidance
```

Hai lệnh trên là **dry-run/read-only**. Sau khi xem diff dự kiến, cài **mặc định STRICT**:

```sh
python3 tools/agentflow.py --repo "/duong/dan/repo" install-guidance --apply
```

Installer chỉ thêm managed blocks vào `AGENTS.md` và `CLAUDE.md`, giữ mọi nội dung bên ngoài; backup vào `~/Library/Application Support/AgentWorkflowV3/guidance_backups/`. Không cài hooks, không gọi Codex/Claude, không thêm UI, không đổi quyền filesystem và **không cấp khả năng ghi**.

### Để thực sự làm việc coding sớm bằng công cụ hiện có

**Tùy chọn `ADVISORY` cần lựa chọn rõ ràng của bạn**: agent được hướng dẫn chờ bạn duyệt Task Contract ngay trong chat rồi có thể dùng tool/permission **sẵn có** của Codex/Claude để sửa những phần đã thỏa thuận. Đây là **quy ước quy trình, KHÔNG phải Strict Approval được OS cưỡng chế**; không thể chống agent bypass một cách chắc chắn. Không dùng như lớp bảo vệ repo nhạy cảm.

```sh
# Xem thay đổi khi chuyển mode
python3 tools/agentflow.py --repo "/duong/dan/repo" install-guidance --mode advisory --upgrade
# Chỉ sau khi chấp nhận giới hạn trên:
python3 tools/agentflow.py --repo "/duong/dan/repo" install-guidance --mode advisory --upgrade --apply
```

Trên repo chưa cài, chỉ cần `install-guidance --mode advisory --apply` (không cần `--upgrade`). Có thể giữ `STRICT` để chỉ nghiên cứu/plan và chưa làm code writes.

## 3. Các lệnh agent có thể gọi nếu cần

```sh
python3 tools/agentflow.py --repo "/duong/dan/repo" interact "Sửa một lỗi hiển thị"
python3 tools/agentflow.py --repo "/duong/dan/repo" resume "lỗi hiển thị"
python3 tools/agentflow.py --repo "/duong/dan/repo" repo-status
python3 tools/agentflow.py --repo "/duong/dan/repo" tasks
python3 tools/agentflow.py --repo "/duong/dan/repo" si-release-doctor
```

`interact` có thể tạo **state draft ngoài repo**; `resume` tìm task theo tên và xuất handoff đọc-only. Các tool `propose-contract`, `draft-plan`, `draft-work`, `checkpoint`, `report-check`, `final-review` dùng cho agent/operator; chúng **không tự xác thực approval/PASS**.

## 4. Hoàn nguyên và gỡ

Lệnh cài thành công trả `transaction_id`. Dùng để rollback **đúng bản backup** nếu các file chưa bị sửa sau đó:

```sh
python3 tools/agentflow.py --repo "/duong/dan/repo" rollback-guidance TRANSACTION_ID --apply
```

Hoặc chỉ gỡ các đoạn managed blocks của kit:

```sh
python3 tools/agentflow.py --repo "/duong/dan/repo" remove-guidance --apply
```

Nếu file hướng dẫn đã bị chỉnh sửa sau khi cài, installer/rollback sẽ từ chối ghi đè; cần review thủ công thay vì mất dữ liệu.

## 5. Kiểm tra và bàn giao

```sh
python3 tools/practical_smoke.py        # 20 bước trên repo tạm; không đổi repo của bạn
python3 tools/release_acceptance.py     # regression + Preview + smoke; ghi release/ONE_SHOT_ACCEPTANCE.json
python3 tools/verify_release.py        # kiểm SHA-256 của bản kit đóng gói
```

**Giới hạn cần hiểu:** Không có native write broker, trusted human approval provenance, OS mandatory confinement hoặc integration certification cho bốn provider. Python tests PASS **không đủ** để chuyển G2/G5/G7 sang PASS. Có thể bắt đầu thử **process-only** theo `ADVISORY` trong một repo thử/bản sao; đừng xem đây là bảo đảm an ninh.

## 6. Tài liệu cần đọc

- `guides/01_HUONG_DAN_TICH_HOP.md` — cài, update, doctor, rollback, giới hạn quyền.
- `guides/02_HUONG_DAN_SU_DUNG.md` — cách giao task và làm việc với Codex/Claude hàng ngày.
- `guides/03_BAO_CAO_GIOI_HAN_VA_NGHIEM_THU.md` — kết quả review, các điểm chưa đạt.
- `guides/04_GIAO_THUC_DANH_CHO_AGENT.md` — RIG 8 và EEW 10 trong một luồng.
- `guides/06_DELEGATED_ADVISORY.md` — A1 opt-in, nguồn H/D, digest, thu hồi và giới hạn helper.
- `guides/07_STATUS_PRESENTATION.md` — A2 tách tiến độ, provenance, freshness và mức xác minh.
- `guides/08_CONTINUITY.md` — A3 checkpoint theo mốc và tiếp quản qua phiên mới.
- `guides/09_CHECKED_PATCH_FLOW.md` — sửa A4: guard, checkpoint read-back và patch callback tuần tự.
- `HANDOFF_AGENT_PROMPT_V3.md` — prompt đầy đủ để agent khác tiếp quản **audit/report trước, không tự scale**.
- `docs/MVP_SCOPE_AND_DECISIONS.md` — những nội dung được chốt và không được tự mở rộng.

Các bản thiết kế, source-preview và báo cáo Đ0–Đ2.1/SI trước đó vẫn có trong ZIP để đối chiếu/hồi quy; **không phải** cấu hình cần cài vào mỗi repo.
