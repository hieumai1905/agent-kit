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
