> **Mốc hiện hành v1.0 — 02/11/2026:** Snapshot readiness ngày 30/10, giữ làm lịch sử; các dòng “chưa cài/chưa chạy” bên dưới không là trạng thái hiện tại. v1.0: V1_0_ACCEPTANCE.json và ../README_START_HERE.md.

# Kết quả sửa lỗi và mức sẵn sàng pilot

**Bản:** `3.0-practical-integration.2` — **30/10/2026**

**Quyết định: `READY_FOR_REPO_PILOT`**, trong phạm vi thử nghiệm tuần tự, có kiểm soát, dùng ADVISORY sau khi người dùng chọn rõ mode. Đây là trạng thái sẵn sàng bắt đầu phép thử trên Concat; chưa phải kết luận workflow đã hiệu quả trên Concat hay đã tích hợp E2E với cả bốn provider.

## Những lỗi đã xử lý

| Hạng mục từ audit | Thay đổi và kiểm chứng |
|---|---|
| Installer làm đổi CRLF/newline ngoài block | Đọc và backup theo byte; ghi nhận phần separator do kit thêm; uninstall giữ nguyên nội dung bên ngoài. Đã kiểm round-trip install/upgrade/rollback/remove với CRLF, LF, whitespace và file không có newline cuối. |
| Cài thất bại ở file thứ hai, rollback bị chặn | Lỗi apply trả transaction ID/backup path. Rollback nhận diện before/after từng file, phục hồi phần đã ghi và giữ phần chưa ghi; từ chối phiên bản người dùng sửa mới. Có thể gọi lại sau phục hồi dở. |
| Helper bỏ mất state-home | Giữ state-home đã chọn trong helper command; backup và state cùng tuân theo AGENTFLOW_STATE_HOME. |
| Kit di chuyển bị coi là customized | Nhận diện hai helper commands có path thay đổi, vẫn yêu cầu toàn bộ policy text khớp mẫu đã biết. Custom rules vẫn bị từ chối ghi đè/xóa. Upgrade từ kit `.1` thực tế và rollback về byte trước nâng cấp đã qua. |
| Doctor bỏ sót override | Báo AGENTS.override.md và giữ trạng thái provider loading UNVERIFIED; không tự sửa override. |
| Contract có blocking gaps/open questions vẫn READY | Kiểm blocking gaps cho cả Quick; câu hỏi chưa giải quyết có ảnh hưởng quyết định chặn readiness. Câu hỏi ghi rõ nonblocking không làm phình Quick workflow. Không cấp approval hay quyền OS. |
| Handoff mất scope/ràng buộc, plan cũ không được báo | Trả đầy đủ nội dung contract; gắn freshness CURRENT/STALE/UNBOUND cho plan/work graph; DAG mới có contract hash/revision. |
| Resume mơ hồ không hiện lựa chọn | Khi không khớp tên, hiển thị recent task choices; không tự chọn theo độ mới. |
| Race khởi tạo SQLite | Retry có giới hạn riêng bước journal_mode=WAL gặp SQLITE_BUSY/LOCKED; không retry mù thao tác ghi. Đã thử 20 vòng, mỗi vòng 4 tiến trình cùng khởi tạo, không gặp lỗi. |
| Test/report sai trạng thái trên Mac | Canonicalize path trong hai assertion; runner tính G1 theo regression thực tế, nhận kết quả OK có skipped và báo riêng số pass/skip. Bỏ 7 định nghĩa test trùng tên, không giảm số test thực chạy. |

Không thêm schema migration, package dependency, hook, service, UI, provider execution engine hoặc cơ chế đổi model. Không phát triển thêm SI/EA.

## Bằng chứng trên Mac

- macOS/Darwin arm64; Python CLI 3.11.5.
- `python3 tools/release_acceptance.py`: exit **0**, 330 test được phát hiện: **329 qua, 1 bị bỏ qua**, không failure/error. Regression 325 gồm 324 qua + 1 skip; Preview 5 qua.
- Test xattr bị bỏ qua vì Python CLI không có API tương ứng; không tính nó thành PASS hay native certification.
- Scratch smoke **9/9** và practical scratch E2E **20/20** qua; fixture mã sản phẩm không đổi.
- Chạy lại **33/33 scenarios** từ audit độc lập: qua, bao gồm những ca trước đó thất bại.
- Stress first-use state: **20 vòng / 80 tiến trình**, **0 lỗi quan sát được**. Mẫu này không chứng minh không bao giờ có lỗi hoặc hard multiwriter safety.
- Thêm **13 regression tests** gắn với lỗi thực tế và cách báo skipped/gate.
- `release/ONE_SHOT_ACCEPTANCE.json`: kết quả runner hiện hành; `release/PILOT_VALIDATION.json`: tổng hợp, định danh code và giới hạn.

Tệp PDF, báo cáo RC.1/SI, handoff và baseline ngày 29/10 trong gói được giữ như tài liệu lịch sử `.1`. Dùng README, tài liệu pilot này và JSON hiện hành để đánh giá `.2`.

## Những gì chưa được tuyên bố

- Chưa đọc mã nguồn hoặc cài workflow vào `/Users/Documents/test-agent/Concat`.
- Chưa khởi chạy phiên model/provider mới, chưa kiểm việc tự nạp instructions trong một phiên mới trên cả bốn môi trường.
- Native trusted approval và mandatory write boundary: **G2/G5 vẫn BLOCKED**. STRICT vẫn là guidance fail-closed, không có bảo đảm OS do kit cung cấp.
- Resource intents/Git previews hỗ trợ phối hợp logic; không bảo vệ mọi đường ghi của hai agents thật. Pilot đầu chạy tuần tự.
- Chưa đo rework, token usage hoặc thời gian trong Concat; không khẳng định mức tiết kiệm hoặc hiệu quả tối đa trước khi có dữ liệu.
- `.2` bảo toàn byte được nhận khi cài/nâng cấp. Không thể khôi phục CRLF gốc đã bị `.1` normalize nếu không còn backup raw ban đầu.

## Bắt đầu Concat

Đọc `guides/05_CONCAT_PILOT.md`. Bước kế tiếp là onboarding **read-only**: instructions hiện hành, Git và scripts của Concat; dry-run rồi review. Sau khi xác định mode và phạm vi cài, mở phiên provider mới xác nhận instructions, làm một task Quick thật, kiểm diff/test và thử resume.

Không cần thêm tính năng trước bước này. Các vấn đề tiếp theo chỉ được ưu tiên nếu quan sát được trong pilot và có tác động đến correctness, continuity hoặc thao tác của người dùng.
