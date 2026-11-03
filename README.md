# Agent Workflow Kit

Workflow cho coding agent trong dự án hiện tại: **hiểu việc → contract ngắn → duyệt → sửa và kiểm chứng → bàn giao**.

[MIT License](LICENSE) · Python 3.11+ · Git · **v1.1.0-slim-candidate.2 — bản thử**

## Bắt đầu

Mở agent tại thư mục dự án rồi dán prompt trong [INIT_PROMPT.md](INIT_PROMPT.md). Agent clone đúng phiên bản ra ngoài dự án, kiểm manifest, preview/setup và đọc lại AGENTS.md/CLAUDE.md để áp dụng workflow. **Thư mục đang làm việc khi nhận prompt là đích mặc định.** Setup giữ luật riêng, backup, state/history và các thay đổi đang có.

Prompt chỉ áp dụng khi người dùng chủ động gửi vào chat cần setup. Việc phát hành không tự nâng cấp hoặc điều khiển các chat đang chạy. Cách nâng cấp tại điểm dừng an toàn: [BOOTSTRAP.md](BOOTSTRAP.md).

Có thể [tải ZIP của tag](https://github.com/hieumai1905/agent-kit/archive/refs/tags/v1.1.0-slim-candidate.2.zip) rồi setup thủ công:

```sh
python3 -B /ABS/KIT/tools/verify_release.py
python3 -B /ABS/KIT/tools/agentflow.py --repo /ABS/PROJECT setup --mode advisory --upgrade
python3 -B /ABS/KIT/tools/agentflow.py --repo /ABS/PROJECT setup --mode advisory --upgrade --apply
```

Preview trước apply. Tracked/mixed guidance, block tùy biến, artifact trong INDEX hoặc override chưa giải quyết phải BLOCKED; không tự untrack/unstage, ignore rộng hoặc ghi đè luật riêng. SETUP_LOCAL_READY chưa chứng minh agent đã áp dụng hướng dẫn trong session.

## Giao việc bình thường

> Sửa lỗi [triệu chứng], kết quả mong muốn [kết quả]. Giữ nguyên [ràng buộc]. Không commit/push/deploy.

Agent đọc phần liên quan và trình contract ngắn: outcome, scope, ví dụ phải sửa, ví dụ phải giữ và checks. Bạn duyệt một lần cho đúng phạm vi. Hỏi/khảo sát/đề xuất trả lời trực tiếp, chưa tạo metadata triển khai. Không tự biến giả định chưa xác nhận thành yêu cầu.

Luồng thường dành cho một batch trong một Git root:

| Mốc | Helper thực hiện |
|---|---|
| `work begin` | Lưu quyết định USER đã duyệt, đọc lại và kiểm trước patch; trả receipt |
| `work verify` | Chạy checks đã khai báo, lưu log/exit và binding tested sources |
| `work handoff` | Kiểm scope/freshness/artifacts/INDEX và lưu kết quả cùng bàn giao |

Helper mang IDs/revisions/hashes; người dùng không nhập JSON/IDs. Agent dùng receipt mới nhất. Xem [SLIM.md](docs/SLIM.md) để biết flags và ví dụ. Nhiều repo, refinement/batch tiếp, migration, security/permissions, billing, delegation hoặc handoff dài dùng API nâng cao trong [USAGE.md](docs/USAGE.md); không bắt task nhỏ đọc toàn bộ quy trình.

Không hỏi lại quyền đã duyệt trong scope. Không chuyển approval/PASS cũ sang contract/source mới. Unit/mock không chứng minh UI thật; bàn giao phải nói rõ mức kiểm chứng và phần còn thiếu. Handoff thành công không tạo báo cáo/checkpoint trùng.

## File vận hành và giới hạn

Clone/runtime/state/receipt/log/report của kit nằm ngoài product tree. Chỉ hai guidance kit-only chưa tracked được đặt tại root bằng Git local exclude hẹp. Product regression tests vẫn thuộc code sản phẩm. Checker đọc INDEX blobs và marker/fingerprint/state; receipt/baseline vẫn được nhận diện khi đổi định dạng JSON, log kit có marker riêng. Không tự sửa product .gitignore/hooks/global config hoặc bỏ tracked files để lách kiểm tra.

Đây là **ADVISORY**, không phải OS sandbox, xác thực người gửi hay khóa cưỡng chế mọi commit. State/receipt không cấp quyền. Commands chạy theo quyền hiện có; tests là executable code. Baseline chỉ bao phủ Git-visible files và các quan sát có giới hạn. Mapping checks→acceptance/preserve vẫn cần review nghĩa. Không tự cài dependencies, đổi model/settings, thêm agents hoặc stage/commit/push/deploy.

`VERIFIED_REPORTED` là mức đủ của báo cáo, không phải trusted verification. CLI nâng cao/schema state/history được giữ; gỡ guidance không xóa lịch sử. Một writer, không tự tạo/gia hạn delegation. Không thêm model/API calls vào runtime.

## Mức kiểm thử

Bản rút gọn qua sàng lọc hai ca lỗi lịch sử: 21/21 và 9/9 tiêu chí code cùng regression liên quan. Ở một cặp hoàn tất cùng mức core quality, helper giảm 11→3 lần gọi; thời gian giảm khoảng 15%, output giảm khoảng 15%, nhưng uncached input tăng khoảng 17%. Cặp còn lại có control timeout nên không dùng tính phần trăm tiết kiệm.

**Chưa xác nhận giảm tổng usage/chi phí, chưa chạy đủ vòng đối chứng lặp lại và chưa nghiệm thu UI thật.** Đây là bản thử, không phải kết luận agent quyết định tốt hơn ở mọi dự án. Trace/snapshot dự án và dữ liệu kiểm thử riêng không thuộc gói người dùng.

```sh
python3 -B /ABS/KIT/tools/verify_release.py
python3 -B /ABS/KIT/tools/practical_smoke.py
```

Smoke dùng fixture tạm, không gọi model hay sửa dự án thật. [BOOTSTRAP.md](BOOTSTRAP.md) và [USAGE.md](docs/USAGE.md) hướng dẫn nâng cấp/gỡ/rollback. Debug/continuity chỉ đọc khi cần: [VERIFICATION.md](docs/VERIFICATION.md), [CONTINUITY.md](docs/CONTINUITY.md).

Copyright © 2026 hieumai1905. [MIT License](LICENSE).
