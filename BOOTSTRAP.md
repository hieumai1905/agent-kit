# Setup / upgrade v1.1.1

Dùng INIT_PROMPT.md mặc định: clone tag v1.1.1 vào thư mục ngoài dự án, xác minh peeled commit/HEAD/remote tag và manifest. Không dùng main/latest hoặc bản cũ thay thế khi kiểm tra không khớp.

Yêu cầu: Git và Python 3.11+ có sẵn. Không tự cài dependencies.

1. Chốt TARGET_CWD bằng pwd -P trước khi đổi thư mục. Phải là Git root người dùng đang làm; không tự chọn repo con/cha, git init hoặc setup hàng loạt.
2. Xác minh manifest bằng python3 -B KIT/tools/verify_release.py. Dùng lại state-home ngoài dự án nếu đã có; giữ nguyên task/history và thay đổi chưa commit.
3. Preview setup ADVISORY; kiểm tra AGENTS.md, CLAUDE.md, override và luật ngoài managed block. Chỉ nâng cấp block cũ được nhận diện chính xác; lưu backup. Tracked/mixed/customized/conflicting guidance phải báo BLOCKED, không unstage/untrack/xóa luật để đi tiếp.
4. Apply đúng preview tại điểm dừng ghi an toàn. Writer bận không được tự takeover. Chỉ hai guidance kit-only được local-exclude bằng .git/info/exclude; không sửa .gitignore/hooks để che sản phẩm.
5. Đọc lại guidance trong chat hiện tại. Doctor, artifacts/INDEX, version và đối chiếu source/index/HEAD sau setup phải đạt trước SETUP_READY. Guidance cài được nhưng nguồn đổi bất ngờ vẫn chưa SETUP_READY; giữ thay đổi và đối chiếu, không tự revert.

Prefix: python3 -B KIT/tools/agentflow.py --repo TARGET_CWD --state-home EXISTING_EXTERNAL_STATE. Xem lệnh setup --help nếu cần chọn --upgrade cho block cũ. Không làm lại setup/doctor mỗi task nếu trạng thái không đổi.

Setup chỉ cấp phạm vi cài guidance/state. Việc code sau đó theo scope USER thực tế. Sử dụng thường ngày: docs/QUICKSTART.md. Không cập nhật chat khác hay phát hành Git tự động.
