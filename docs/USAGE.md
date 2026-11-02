# Sử dụng hằng ngày

Sau SETUP_READY, chỉ gửi yêu cầu bằng ngôn ngữ bình thường. Một agent ghi tuần tự trong project.

## Giao việc mới

> Sửa lỗi [mô tả]. Kết quả mong muốn là [kết quả]. Giữ nguyên [hành vi/ràng buộc]. Không commit/push/deploy.

Agent khảo sát Git/source liên quan và trình contract ngắn. Đọc mục tiêu, phạm vi, phần giữ nguyên và cách kiểm thử; nếu đồng ý, trả lời **Duyệt contract này**. Agent lưu checkpoint quyết định trước patch, triển khai đúng scope, kiểm thử và báo nghiệm thu.

## Tiếp tục

> Tiếp tục việc [tên việc]. Đọc checkpoint và đối chiếu Git/contract/quyết định hiện tại trước khi làm.

Không cần nhớ Task ID hoặc điền JSON. Khi có nhiều việc cùng chủ đề, chọn đúng tên việc. Approval/state từ phiên cũ không tự cấp lại quyền hoặc H/D đã hết hiệu lực.

## Khi agent báo lỗi

- Guard/checkpoint conflict: dừng flow, đọc lại source/state và reconcile trước lần chạy mới; không bypass guard.
- Test fail: xem failure thực tế; chỉ sửa trong scope được duyệt hoặc trình contract điều chỉnh.
- RECOVERY_REQUIRED: giữ DB gốc; kiểm backup và phục hồi vào state mới. Không tự xóa/ghi đè state đang dùng. RETRY_OR_RECONCILE là state đang bận/khóa, không tự suy DB hỏng.
- Override/custom managed block: giải quyết instruction conflict rõ ràng trước SETUP_READY; không xóa quy tắc riêng để ép cài.

## Cập nhật

Không pull/reset đè clone đang sửa hoặc di chuyển/xóa kit được project tham chiếu. Với phiên bản mới, clone tag mới vào thư mục riêng bên ngoài project, verify rồi dùng installer dry-run/upgrade/apply. Bắt buộc đọc lại AGENTS.md và CLAUDE.md và kiểm helper path/mode/override. Nội dung riêng ngoài managed block phải được giữ nguyên.

## File của kit và commit sản phẩm

Kit là công cụ local: clone, state/DB, backup, contract/checkpoint của kit, log, báo cáo, inventory và file tạm phải ở ngoài working tree. Chỉ guidance local cần ở project root; file kit-only chưa tracked phải được loại bằng Git local exclude theo [BOOTSTRAP mục 4.1](../BOOTSTRAP.md#41-kit-local-only-và-bảo-toàn-commit-sản-phẩm). Không thêm `.gitignore` vào commit chỉ để cấu hình kit. Giữ quy tắc này ngoài managed block trong hai file guidance để lần mở chat sau vẫn đọc được.

Trước/sau staging được người dùng duyệt riêng, agent phải đối chiếu inventory và **nội dung index**, không chỉ working tree. Artifact kit trong staged diff phải chặn việc tiếp tục commit. Không tự force-add, untrack, unstage hoặc sửa history; file tracked/mixed cần quyết định rõ. Contract/schema/docs/tests của tính năng sản phẩm vẫn thuộc phạm vi review bình thường, không ignore rộng theo tên thư mục.

v1.0.2 chưa có hook chặn commit: local exclude ngăn thêm nhầm thông thường, còn kiểm index là bước quy trình bắt buộc. Người dùng/agent cố tình vượt ignore vẫn có thể commit trực tiếp; không báo đã có cưỡng chế kỹ thuật.

## Gỡ hoặc rollback

Agent chạy từ thư mục kit, thay placeholders bằng đường dẫn đã xác định và giữ state-home đang dùng:

```sh
python3 -B tools/agentflow.py --repo /ABS/PROJECT remove-guidance
python3 -B tools/agentflow.py --repo /ABS/PROJECT remove-guidance --apply
python3 -B tools/agentflow.py --repo /ABS/PROJECT rollback-guidance TRANSACTION_ID --apply
```

Review dry-run trước khi gỡ. Rollback chỉ phục hồi backup tương ứng khi file chưa thay đổi sau cài. Không tự rollback để đè thay đổi mới; gỡ guidance không xóa task/state ngoài project.

## Kiểm tra kit

```sh
python3 -B tools/verify_release.py
python3 -B tools/practical_smoke.py
```

Smoke chỉ chạy trên repo/state tạm, không gọi model hoặc sửa project thật. Báo cáo local sinh ra dưới release/PRACTICAL_SMOKE.json được Git ignore và không có sẵn trong gói.
