# Agent Workflow Kit v1.0.1

**Phiên bản phân phối: 1.0.1 · 02/11/2026 · Đã chốt phạm vi, tạm dừng mở rộng.**

Bộ hướng dẫn và công cụ local để làm việc với coding agent ngay trong repo. Engine/guidance V3 và schema state giữ nguyên; v1.0.x là dòng bản phân phối thực dụng, không phải triển khai lại hệ thống.

**Bắt đầu tại [hướng dẫn ngắn](guides/00_BAT_DAU_V1_0.md).** Trên Concat hiện tại guidance đã được cài; không cần cài lại hoặc thay đổi repo chỉ để dùng bản v1.0.1. Giữ thư mục kit ở vị trí hiện tại vì guidance tham chiếu helper tại đó.

**Bản vá 1.0.1:** tìm chính xác task cũ ngoài 200 mục gần nhất; tạo intake task/brief/alias trong một transaction; kiểm kiểu và chặn plan/scope rỗng hoặc placeholder; lỗi SQLite đã biết có phản hồi phục hồi rõ ràng; discovery liệt kê nested manifest và CI trong giới hạn. Draft cũ vẫn đọc được. Không đổi schema/dependency, không tự sửa dữ liệu cũ hoặc cài lại guidance vào Concat. ZIP v1.0 giữ nguyên.

## Phạm vi sử dụng

- Codex trên Mac hiện tại, một executor ghi tuần tự, ADVISORY đã được chọn rõ.
- Yêu cầu → contract được duyệt → checkpoint quyết định → patch đúng phạm vi → test/review → handoff.
- Người dùng giao việc bằng tiếng Việt bình thường; agent xử lý Task ID và các lệnh phụ trợ.
- Dùng đúng quyền/tool hiện có của provider. Kit không cấp quyền OS; STRICT vẫn là mặc định của installer. H/D chỉ dùng khi ủy quyền qua chat khác và phải có quyết định còn hiệu lực.
- Không tự stage/commit/push/deploy, thay dependencies hoặc mở rộng phạm vi. Bản v1.0 không bổ sung chức năng, schema, service hay dependency mới.

[Phạm vi được duyệt](release/V1_0_SCOPE.md) là mốc vận hành. Bằng chứng thực tế giới hạn ở pilot Codex trên Concat và CLI tiếp nhận read-only; chưa chứng nhận Claude, mọi task/provider hoặc nhiều writer đồng thời.

## Kết quả và nguồn hiện hành

| Tài liệu | Dùng để làm gì |
|---|---|
| [V1_0_1_ACCEPTANCE.json](release/V1_0_1_ACCEPTANCE.json) | Nghiệm thu bản vá hiện hành F1–F5 và bảo toàn Concat |
| [V1_0_ACCEPTANCE.json](release/V1_0_ACCEPTANCE.json) | Lịch sử nghiệm thu v1.0 được giữ nguyên |
| [ONE_SHOT_ACCEPTANCE.json](release/ONE_SHOT_ACCEPTANCE.json) | Regression/smoke local mới nhất; báo riêng skip |
| [A4_RETRY_ACCEPTANCE.json](release/A4_RETRY_ACCEPTANCE.json) | Pilot thực tế: guard stale dừng patch, checkpoint trước patch, 4/4 test Concat PASS, resume mới đúng task |
| [HANDOFF_AGENT_PROMPT_V3.md](HANDOFF_AGENT_PROMPT_V3.md) | Prompt ngắn để agent tiếp nhận v1.0 |
| [guides/09_CHECKED_PATCH_FLOW.md](guides/09_CHECKED_PATCH_FLOW.md) | Luồng guard/checkpoint của delegated ADVISORY và giới hạn |

A4 lần đầu vẫn **WORKFLOW FAIL**, giữ nguyên ở `release/A4_ACCEPTANCE.json`. Retry đạt trong phạm vi đã duyệt, có erratum một message ID; transcript gốc xác nhận native refresh đã đọc commentary mới. Không xóa lịch sử này hoặc suy PASS toàn hệ thống từ pilot.

`release/A1_ACCEPTANCE.json`, `A2_ACCEPTANCE.json`, `A3_ACCEPTANCE.json`, `PILOT_READINESS.md`, `PILOT_VALIDATION.json`, `guides/03_*`, `guides/05_*`, `docs/`, `native/` và `source-preview/` chứa thiết kế/kết quả tại từng mốc. Ngoại lệ trong `docs/`: các bản trước v1.0 được giữ nguyên dưới `docs/history/`. Không dùng số test hoặc backlog trong tài liệu lịch sử để thay trạng thái hiện hành hay tự mở rộng dự án.

## Kiểm tra gói

Chạy từ thư mục kit:

```sh
python3 -B tools/verify_release.py
python3 -B tools/release_acceptance.py
```

Runner chỉ dùng repo/state tạm và cập nhật hai báo cáo local trong `release/`; không sửa Concat, không gọi model/provider. Manifest không hash hai báo cáo có thể chạy lại (`ONE_SHOT_ACCEPTANCE.json`, `PRACTICAL_SMOKE.json`); checksum ZIP bao phủ toàn bộ bản giao. Checksum kiểm tính toàn vẹn, không xác thực nhà phát hành.

Chỉ dùng `tools/build_practical_release.py` nếu chủ động đóng gói lại v1.0.1. Các builder RC/SI khác là lịch sử. ZIP mới tên `Agent_Workflow_Kit_v1.0.1_2026-11-02.zip`, thư mục bên trong vẫn `Agent_Workflow_V3_Repo_Kit`; ZIP baseline 30/10 được giữ nguyên.

## Giới hạn và đóng băng

ADVISORY là quy ước làm việc. `checkedPatchFlow` chặn callback patch trong luồng được quản lý khi precondition lỗi; agent vẫn có thể gọi tool ghi khác. Chưa có OS enforcement, trusted approval adapter, chống sửa cùng UID, thu hồi nguyên tử hoặc multiwriter safety. G2/G5 vẫn BLOCKED đối với mục tiêu chứng nhận bảo mật lịch sử; v1.0 không phải FINAL/ENFORCED của kiến trúc đó.

Sau bàn giao, dùng kit cho công việc thật theo contract nhỏ và kiểm thử phù hợp. **Tạm dừng phát triển mở rộng.** Chỉ xử lý lỗi cản trở sử dụng khi người dùng giao; không tự triển khai backlog SI/EA, thêm app/daemon, đổi provider/model hoặc mở thêm pilot.
