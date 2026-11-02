> **Mốc hiện hành v1.0 — 02/11/2026:** Kế hoạch pilot lịch sử, không chạy lại các bước cài từ tài liệu này. Trạng thái hiện hành: ../release/V1_0_ACCEPTANCE.json; cách dùng: 00_BAT_DAU_V1_0.md.

# Pilot Concat — kiểm chứng workflow trong dự án thật

Bản kit `3.0-practical-integration.2`, 30/10/2026. Tài liệu này chuẩn bị phép thử; chưa cài hoặc sửa repository Concat.

**Cập nhật A1, 02/11/2026:** bản kit làm việc đã có protocol ủy quyền opt-in; xem `06_DELEGATED_ADVISORY.md`. A1 chỉ triển khai và kiểm local trong kit. Guidance mới chưa cài vào Concat; không chạy lệnh cài từ tài liệu này nếu chưa có dry-run/diff và quyết định riêng. Các bước ngày 30/10 bên dưới là kế hoạch pilot ban đầu, không phải báo cáo tình trạng repo hiện tại; kết quả pilot trước nằm ngoài kit trong hồ sơ dự án.

## Mục tiêu và phạm vi

Đo xem workflow có giúp hiểu đúng yêu cầu, giữ scope, test đúng và tiếp tục công việc hiệu quả trên Concat hay không. Bắt đầu bằng một task Quick ít rủi ro, một session, một working tree. Chỉ mở thử nhiều session sau khi luồng tuần tự hoạt động.

Không cần app/service/hook mới. Dùng permissions hiện có của provider. ADVISORY là quy ước duyệt trong chat, không phải security enforcement. STRICT mặc định chỉ dành cho đọc, phân tích và draft khi G2 chưa có chứng nhận.

## 1. Onboarding read-only của Concat

Trong lượt pilot tiếp theo, mở đúng `/Users/Documents/test-agent/Concat`. Agent kiểm tra instructions đang có, Git status/diff, scripts và conventions liên quan trước. Giữ mọi thay đổi chưa commit; không tự stash/reset/commit, không cài dependencies và không chạy build/test có tác dụng phụ trước khi hiểu scripts.

Từ kit đặt ổn định ở `/Users/Documents/test-agent/Agent_Workflow_V3_Repo_Kit`:

```sh
python3 tools/agentflow.py --repo "/Users/Documents/test-agent/Concat" doctor
python3 tools/agentflow.py --repo "/Users/Documents/test-agent/Concat" install-guidance
```

Hai lệnh trên không áp dụng thay đổi. Doctor báo installed không có nghĩa provider đã loaded. Nếu có AGENTS.override.md hoặc rules khác xung đột, trình nội dung cần hòa giải; không tự sửa file riêng của dự án.

## 2. Chọn mode và cài hướng dẫn

Chỉ dùng ADVISORY khi người dùng đã chọn rõ chế độ này cho pilot. Không suy từ câu duyệt task. Sau khi review thay đổi, agent có thể áp dụng các lệnh tương ứng với quyết định đã có:

```sh
# Repo chưa cài: ADVISORY opt-in
python3 tools/agentflow.py --repo "/Users/Documents/test-agent/Concat" install-guidance --mode advisory --apply
# Nếu đã có bản STRICT: xem trước rồi explicit upgrade
python3 tools/agentflow.py --repo "/Users/Documents/test-agent/Concat" install-guidance --mode advisory --upgrade
python3 tools/agentflow.py --repo "/Users/Documents/test-agent/Concat" install-guidance --mode advisory --upgrade --apply
```

Không chạy cả fresh-install và upgrade một cách máy móc. Nếu giữ STRICT, dùng `install-guidance --apply` để cài chỉ dẫn đọc/draft. Lưu transaction ID từ kết quả. Agent kiểm diff hai file hướng dẫn, không stage chúng. Nếu dùng state home riêng, thêm cùng `--state-home` ở trước subcommand; lệnh helper sinh ra sẽ giữ vị trí đó.

Sau cài, bắt đầu phiên mới trong đúng repo. Prompt đầu tiên:

> Đọc instructions đang có hiệu lực trong repo này. Báo nguồn instructions, mode Agent Workflow, các quy tắc riêng của Concat và giới hạn quyền. Chỉ read-only; chưa sửa file. Nếu instructions xung đột, nêu rõ trước khi làm.

Chỉ đánh dấu provider integration PASS sau khi quan sát được bước này. Không dùng kết quả từ Codex CLI để suy cho Codex Desktop hoặc Claude.

## 3. Một Quick task có đầu ra kiểm chứng được

Chọn lỗi/thay đổi thật nhưng nhỏ sau khi đã đọc Concat; chưa ấn định file hoặc tính năng khi chưa có bằng chứng. Tránh auth, payment, schema migration hoặc deploy trong task đầu.

Agent trình một Task Contract ngắn: kết quả, hành vi giữ nguyên, scope/exclusions, rủi ro và 1–2 acceptance checks. Người dùng duyệt đúng revision; trả lời làm rõ không phải approval. Sau đó agent thực hiện trong ADVISORY bằng tools sẵn có, test tập trung theo scripts đã kiểm tra, review diff rồi báo kết quả/nguy cơ/check NOT_RUN. Không tự commit/push/deploy.

Không yêu cầu người dùng nhập Task ID hoặc JSON. Không tạo SPEC/ADR/DAG file riêng cho việc một dòng nếu chat contract đã đủ. Agent chỉ gọi state helper ở các mốc cần continuity: ghi contract/checkpoint và kết quả được báo, giữ nhãn UNVERIFIED theo khả năng kit.

## 4. Tiếp quản và xung đột

Sau task đầu, checkpoint gồm full contract, file đã đổi, test đã chạy và next action. Phiên mới nói “Tiếp tục công việc vừa làm”; agent gọi resume theo tên, hoặc hiển thị recent choices khi mơ hồ. Không tự chọn task chỉ vì mới nhất.

Đọc lại Git hiện tại. Handoff phải có scope/preserve/exclusions. Nếu artifact STALE hoặc UNBOUND, revalidate trước khi dùng, không nhận plan cũ là quyền thực thi. Approval trong DB/handoff không cấp quyền cho phiên mới.

Ở lượt kiểm thử riêng, dùng hai task độc lập và quan sát resource/Git conflicts. Bắt đầu bằng preview; chưa để hai agent sửa chung một file, Git index hoặc test DB. Metadata intents là phối hợp tự nguyện; chưa có hard concurrency enforcement.

## 5. Đánh giá hiệu quả

Ghi một hàng cho mỗi task, ngay trong báo cáo pilot; không tạo hệ thống telemetry:

| Task/provider | Thời gian đến diff hữu ích | Số lượt làm rõ/duyệt | Số lần sửa lại do hiểu sai | Acceptance đạt/thiếu | Tests thực chạy | Resume đúng/sai | Usage có nguồn |
|---|---|---|---|---|---|---|---|
| Task đầu | Chưa đo | Chưa đo | Chưa đo | Chưa test | NOT_RUN | Chưa test | UNKNOWN |

So hiệu quả qua vài task đại diện sau khi có dữ liệu; không tự khẳng định tiết kiệm token hoặc “hiệu quả tối đa”. Quality đạt trước, rồi mới rút bước gây phiền đã quan sát. Không chạy release acceptance/SI/security labs cho mỗi task.

Điều kiện pilot thành công: đúng instructions và mode, contract đủ quyết định, diff đúng scope, tests/evidence trung thực, không làm mất thay đổi khác, resume giữ ràng buộc, gỡ/rollback hướng dẫn được kiểm chứng. Check nào chưa thử vẫn NOT_TESTED; security G2/G5 vẫn BLOCKED.

## 6. Rollback

```sh
python3 tools/agentflow.py --repo "/Users/Documents/test-agent/Concat" rollback-guidance TRANSACTION_ID --apply
```

Rollback chỉ phục hồi các phiên bản before/after đã biết; từ chối nội dung người dùng sửa mới. Không rollback mã sản phẩm hoặc xóa state. Có thể gỡ managed blocks bằng `remove-guidance --apply`; phần nội dung khác được giữ nguyên. Nếu apply báo incomplete, dùng transaction ID/backup path trong lỗi để phục hồi, không ghi đè thủ công một cách mù quáng.
