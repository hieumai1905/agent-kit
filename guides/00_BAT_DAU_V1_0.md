# Bắt đầu dùng Agent Workflow Kit v1.0.x

**1.0.1 · 02/11/2026 · Codex, một agent ghi tuần tự, ADVISORY.**

## Dùng ngay trên Concat hiện tại

1. Mở Concat trong Codex. Giữ thư mục kit ở vị trí đang dùng; guidance và helper đã có, không cần cài lại.
2. Gửi yêu cầu theo mẫu:

> Đọc AGENTS.md và kiểm tra Git trước. Tôi muốn [kết quả cần đạt]. Giữ nguyên [hành vi/phần không được đổi]. Trình contract ngắn trước khi sửa. Sau khi được duyệt, lưu checkpoint quyết định trước patch, kiểm thử và báo nghiệm thu. Không stage/commit/push/deploy.

3. Đọc contract: mục tiêu, file/phạm vi, phần giữ nguyên, rủi ro và cách kiểm thử. Khi đồng ý, trả lời **“Duyệt contract này.”** Nếu còn thiếu, yêu cầu sửa contract trước.
4. Agent thực hiện và báo: file đã đổi, test/check thực chạy, kết quả và giới hạn, Git, checkpoint bàn giao. Bạn kiểm nghiệm thu; task xong không tự đồng nghĩa commit/push/deploy.

Khi tiếp tục việc cũ:

> Tiếp tục việc [tên công việc]. Đọc checkpoint và đối chiếu Git/contract/quyết định hiện tại trước khi làm. Giữ các thay đổi đang có; không tự dùng lại delegation đã kết thúc.

Bạn không cần nhớ Task ID hoặc tự điền JSON. Nếu có nhiều task trùng chủ đề, agent cần hỏi chọn đúng công việc.

## Khi có chat điều phối và chat thực thi

Dùng protocol H/D đã có: bạn duyệt phạm vi ủy quyền cụ thể (H), điều phối duyệt đúng contract (D), executor tự đọc nguồn native và ràng buộc còn hiệu lực. H hết hạn tối đa hai giờ hoặc khi task xong/dừng/thu hồi. Một writer, không chuyển quyền.

Ở nhánh delegated ADVISORY, executor dùng đúng `checkedPatchFlow`: `prepare-write` lưu và đọc lại checkpoint → `check-write` → provider patch. Observation quá 30 giây phải refresh thật; guard lỗi thì dừng flow, không gọi apply_patch riêng. Đây là việc agent thực hiện, không phải thao tác thủ công của bạn. Xem guide 06 và 09 khi cần chi tiết.

## Nếu kit được chuyển vị trí hoặc cài cho repo mới

Không cần bước này để tiếp tục dùng Concat hiện tại. Không di chuyển/xóa kit đang được guidance tham chiếu khi agent đang làm việc. Đặt bản giải nén ở vị trí bền vững ngoài repo, rồi yêu cầu agent kiểm tra helper path và trình dry-run/diff trước khi cài/nâng cấp. Không tự ghi đè custom guidance.

Lệnh tham khảo cho agent, chạy từ kit và thay `/ABS/REPO` bằng repo đã được phép:

```sh
python3 -B tools/verify_release.py
python3 -B tools/agentflow.py --repo "/ABS/REPO" doctor
# Repo mới: dry-run ADVISORY, không ghi
python3 -B tools/agentflow.py --repo "/ABS/REPO" install-guidance --mode advisory
# Sau quyết định cài của người dùng:
python3 -B tools/agentflow.py --repo "/ABS/REPO" install-guidance --mode advisory --apply
```

Với repo đã có managed block, dùng `--upgrade` trong cả dry-run và apply. Chỉ thêm `--delegated-advisory` vào cả hai khi người dùng chọn dùng H/D; không thêm cờ này sẽ chọn luồng duyệt trực tiếp, kể cả khi nâng cấp. Installer luôn mặc định STRICT khi không chỉ định mode.

## Khi có vấn đề

- Dừng/guard lỗi: giữ nguyên hiện trạng, báo phần đã/chưa làm; kiểm tra nguồn/Git trước lần chạy mới, không tự rollback patch.
- Test fail: báo actual failure; chỉ sửa trong phạm vi đang được duyệt hoặc trình thay đổi contract.
- Đổi phiên: handoff/state là dữ liệu chưa xác thực, không cấp quyền ghi. `IMPLEMENTED` có thể đi cùng canonical `WAITING_APPROVAL`; không sửa DB để làm đẹp trạng thái.
- Không cho hai agent cùng ghi working tree. Claude, multiwriter và enforcement ở cấp OS chưa thuộc phạm vi nghiệm thu v1.0.

Bản này dùng lại workflow đã kiểm thử, không cam kết hiệu quả/token savings chưa đo. Tạm dừng mở rộng; chỉ đề xuất sửa lỗi cản trở công việc thật.

## Ghi chú bản vá 1.0.1

Tên/alias khớp chính xác được tìm trong toàn lịch sử; tìm gần đúng vẫn có giới hạn và báo cắt ngắn. Payload sai kiểu hoặc plan/scope trống bị từ chối khi lưu mới; bản ghi draft cũ vẫn đọc được. Nếu CLI báo `RECOVERY_REQUIRED`, giữ nguyên DB và yêu cầu agent kiểm backup/phục hồi sang state mới; không tự xóa hoặc ghi đè state đang dùng. `RETRY_OR_RECONCILE` là state đang bận/khóa, không tự suy là DB hỏng. Discovery nested manifest/CI chỉ liệt kê đường dẫn, không chạy build.
