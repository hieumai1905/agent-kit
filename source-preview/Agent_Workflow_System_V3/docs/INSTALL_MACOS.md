# Cài đặt & kiểm thử trên macOS

## 0. Môi trường

Chỉ cài vào **Git repo root**, không cài theo folder con; hiện tại dùng cùng working tree, không tự tạo worktree. Cài đặt cần Python 3.10+ (`python3 --version`) và Git (`git --version`). Nếu `python3` quá cũ/hết PATH trên GUI, dùng Python Homebrew hoặc python.org và chỉnh đường dẫn interpreter trong các hooks để trỏ đến binary ổn định. Không chạy `curl | sh` từ mạng để cài kit.

## 1. Kiểm tra thay đổi trước khi cài

Trong thư mục chứa ZIP đã giải nén:

```bash
python3 install.py --repo "$HOME/Projects/my-project"
```

Lệnh chỉ hiển thị những file sẽ `CREATE/UPDATE`. Kiểm tra trước `git status --short` và lưu mọi thay đổi chưa commit. Khi đã đồng ý:

```bash
python3 install.py --repo "$HOME/Projects/my-project" --apply
cd "$HOME/Projects/my-project"
python3 .agentflow/bin/agentflow.py doctor
```

Installer giữ các chỉ dẫn đã có trong `AGENTS.md`, `CLAUDE.md`; merge hook settings JSON; copy file workflow nếu chưa tồn tại. Backup nằm ngoài repo. Đọc `OPEN_DECISIONS.md` trước khi để agent tự triển khai dự án quan trọng.

## 2. Thiết lập trong bốn môi trường

**Codex Desktop:** chọn **Local**, đúng folder repo; tin cậy project. Kiểm tra hooks qua `/hooks` hoặc phần cài đặt hỗ trợ. Vì hooks chưa được trust có thể không chạy, test thực tế bằng prompt thử. **Không bật chế độ bỏ qua kiểm soát**.

**Codex CLI:** từ repo root `codex`; gọi `/hooks` để duyệt/trust hooks. Nếu `python3` không có trong PATH, cập nhật `command` trong `.codex/hooks.json` và review/trust lại.

**Claude Desktop tab Code:** chọn Local + folder repo gốc; **Worktree OFF**. Kiểm tra tính năng hooks được hỗ trợ ở phiên bản Code đang chạy (có thể không bằng phiên bản CLI), dùng `/hooks` nếu có. Có thể cần khởi động phiên mới sau khi cài hooks.

**Claude Code CLI:** trong repo root `claude`; dùng `/hooks` để kiểm tra; bảo đảm settings project `.claude/settings.json` được đọc. Không dùng `--worktree` hoặc chế độ bypass permissions khi thử.

**Lưu ý:** App đôi lúc không thừa hưởng đầy đủ shell PATH; cấu hình `python3` theo tuyệt đối nếu việc gọi hook báo `command not found`.

## 3. Kiểm tra trong repo test, KHÔNG dùng repo đang làm việc quan trọng

1. Gửi `Tạo tính năng đổi lời chào ở src/hello.py`.
2. Kiểm tra `docs/agentflow/tasks/T-...` được tạo; agent chưa được sửa `src/`.
3. Cho agent thử sửa `src/hello.py` ngay khi chưa duyệt. Hook phải chặn (nếu không chặn, STOP: tích hợp chưa đạt).
4. Agent nghiên cứu và cập nhật `contract.json`, dùng `propose`, trình SPEC trong chat.
5. Gửi `Duyệt` (đúng session), kiểm tra file được sửa **nếu nằm trong scope**.
6. Sửa thử contract sau duyệt, rồi yêu cầu ghi file; phải bị chặn.
7. Mở session thứ hai cùng folder, giao task khác, thử hai file khác nhau (được qua guard), cùng file (bị chặn). Không thực sự ghi đè dữ liệu quan trọng trong phép thử.
8. Dùng phiên Codex mới hoặc Claude mới với `Tiếp tục T-ID`; đọc STATE + Git diff và khôi phục.
9. Dùng `python3 .agentflow/bin/agentflow.py model-advice T-ID --provider codex`/`claude` để xem gợi ý; chỉ dùng model được cấp quyền.
10. Cấu hình `verification.json` với các lệnh an toàn *thật sự tồn tại*, rồi kiểm chứng. Khi chưa có check phải báo NOT RUN.

Bảng test chi tiết ở `docs/ACCEPTANCE_TESTS.md`.

## 4. Rollback

Installer in đường dẫn `Backup ở: ...`. Khi muốn khôi phục những file do installer tạo/merge, chạy:

```bash
python3 install.py --rollback "/Users/.../Library/Application Support/AgentWorkflow/installation-backups/<repo-hash>/<timestamp>"
```

Rollback chỉ chạy nếu các file vẫn giữ nguyên fingerprint sau lúc cài; nếu đã sửa tiếp thì dừng để tránh mất code của bạn. Runtime DB ở `~/Library/Application Support/AgentWorkflow/<repo-hash>/` được giữ nguyên, không tự xóa dữ liệu lịch sử/approval.

## 5. Cập nhật/hợp nhất

Trước khi áp dụng bản kit mới, review code diff và các hooks, backup lại, rồi dùng installer dry-run. Không ghi đè `model-policy.json`, `verification.json` đã được dự án tùy biến.
