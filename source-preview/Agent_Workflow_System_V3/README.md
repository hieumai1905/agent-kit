# Agent Workflow System V3.0 — bản triển khai nền tảng cho macOS

**Dành cho:** Codex Desktop + Codex CLI, Claude Desktop (Code) + Claude Code CLI; **local, cùng một Git repo và cùng working tree**, chuyển nền tảng **thủ công** khi cần. Không yêu cầu subagent, MCP, API key hay thêm một ứng dụng chat mới.

> **Trạng thái thực tế:** Đây là **bản triển khai tích hợp và policy nền tảng (V3.0 Preview)**, không phải chứng nhận an toàn tuyệt đối. Logic kỹ thuật/prompting/coding style chưa được người dùng chốt sâu, được đặt trong tài liệu `PROPOSED` để cùng thảo luận tiếp. Chưa cài vào máy hoặc repo của bạn. Các hook cần được kiểm chứng trên chính phiên bản desktop/CLI của bạn. Chạy hai agent với cùng quyền macOS có thể vượt qua file-hook nếu tool/path không được intercept. Xem `SECURITY.md`.

## Bộ kit bao gồm

- `install.py`: cài **một lần vào từng repo**; mặc định dry-run, merge cấu hình, backup, rollback có kiểm tra hash.
- `kit/AGENTS.md` + `CLAUDE.md`: nguyên tắc chung, không đè chỉ dẫn sẵn có.
- `kit/.codex/hooks.json`, `kit/.claude/settings.json`: nạp hook ở các sự kiện prompt/tool/session.
- `kit/.agentflow/bin/agentflow.py`: Python + SQLite standard library; tự tạo task, Task Contract, approval trong chat, phạm vi chỉnh sửa, khóa file theo session, checkpoint, model advice và verification.
- `kit/.agents/skills/agent-workflow`, `kit/.claude/skills/agent-workflow`: cùng một Skill hướng dẫn quy trình, không phụ thuộc subagent.
- `kit/docs/agentflow/*`: hướng dẫn sử dụng, giới hạn và những phần thiết kế chưa chốt.
- `tests/`: bài test tích hợp giả lập hook (không thay thế GUI acceptance test).

## Cài đặt trên macOS — thực hiện một lần

Cần Python 3.10+ và Git. Giải nén file ZIP rồi mở Terminal:

```bash
python3 --version
git --version
python3 install.py --repo "/duong-dan/toi/my-project"          # Xem trước thay đổi
python3 install.py --repo "/duong-dan/toi/my-project" --apply  # Chỉ chạy sau khi review
cd "/duong-dan/toi/my-project"
python3 .agentflow/bin/agentflow.py doctor
```

- Installer không tự sửa repo của bạn khi chưa có `--apply`.
- File cũ được giữ/merge, bản sao được lưu tại `~/Library/Application Support/AgentWorkflow/installation-backups/`.
- Với Codex, đánh dấu project và hooks là **trusted**; dùng `/hooks` để kiểm tra.
- Với Claude, dùng `/hooks` để kiểm tra hooks. Chọn **Local** trong Claude Desktop Code và **tắt Worktree** để giữ cùng một folder. Trong Codex Desktop cũng chọn Local và đúng folder repo.
- Giữ quyền của CLI/app ở chế độ bình thường; **không bật bypass permissions**.

Chi tiết: [`kit/docs/agentflow/INSTALL_MACOS.md`](kit/docs/agentflow/INSTALL_MACOS.md).

## Hằng ngày — không cần gõ task ID / scope / risk bằng tay

1. Mở Codex hoặc Claude Code tại repo, nhập yêu cầu tự nhiên như mọi ngày.
2. Hook tự tạo task và đưa chỉ dẫn PREFLIGHT. Agent đọc repo (chỉ đọc) và tự điền `contract.json` dựa trên bằng chứng, hỏi bạn nếu cần.
3. Agent dùng `python3 .agentflow/bin/agentflow.py propose <ID>` để tạo `SPEC.md`, trình toàn bộ bản đặc tả trong chat.
4. **Bạn xem rồi gõ `Duyệt` trong cùng session**. Nếu muốn sửa, viết yêu cầu điều chỉnh; trước đó tuyệt đối không cho sửa code.
5. Khi được duyệt, agent sửa đúng scope. Khi mở session mới hoặc đổi Codex↔Claude, nhắn `Tiếp tục T-...` (hoặc `Tiếp tục` nếu chỉ có một task đang mở).
6. Agent cập nhật `STATE.md`, đối chiếu code/diff, kiểm thử theo cấu hình dự án và báo những phần `NOT RUN`.

**Không cần người dùng chạy `agentctl new`**. Task ID do hệ thống tạo. **Không có tự chuyển Codex↔Claude, không có tự thay model**.

## Giới hạn đã biết — đọc trước khi sử dụng repo quan trọng

1. Hook là **guardrail**, không phải OS sandbox. CLI/app có toàn quyền filesystem vẫn có những đường thực thi nằm ngoài khả năng kiểm soát. **D1-B (hard enforcement) chưa được chứng minh trên máy bạn**.
2. Đồng thời sửa file khác nhau có thể được khóa/cho phép trong các đường `Write/Edit/apply_patch` đã tích hợp. Không có bảo đảm cô lập toàn bộ side effects, shared files, Git index hay commands ngoài hooks. **D3-B được cài cơ chế phối hợp, chưa đạt chứng nhận an toàn tuyệt đối.**
3. Router chỉ gợi ý **tier** `FAST/BALANCED/DEEP` dựa trên độ khó/rủi ro do agent đánh giá; model cụ thể chỉ đề xuất nếu bạn đã cấu hình danh sách được phép. Usage không đọc được sẽ hiển thị `UNKNOWN`; không đoán.
4. Chưa có bộ test mặc định của project; `verification.json` ban đầu trống => `NOT RUN`, không được báo PASS.
5. LLM vẫn là thành phần hiểu yêu cầu; script chỉ kiểm tra cấu trúc/bằng chứng cơ bản, không thể bảo đảm model đã hiểu đúng ý bạn.
6. Với nhiều task trong **cùng một session**, tin nhắn tự nhiên được xem là thay đổi/câu hỏi cho task đang hoạt động cho đến khi model chuyển task; hãy xem [`OPEN_DECISIONS.md`](kit/docs/agentflow/OPEN_DECISIONS.md) để chốt phân loại task mới/phụ.

## Tài liệu nên đọc theo thứ tự

1. `kit/docs/agentflow/INSTALL_MACOS.md` — cài, kiểm tra hooks, rollback.
2. `kit/docs/agentflow/WORKFLOW.md` — trạng thái và hành vi khi giao việc.
3. `kit/docs/agentflow/SECURITY.md` — giới hạn cưỡng chế & multi-writer.
4. `kit/docs/agentflow/REQUIREMENTS_PROPOSED.md` — logic chuẩn hóa prompt cần bàn sâu tiếp.
5. `kit/docs/agentflow/EXECUTION_PROPOSED.md` — coding style / convention / cấu trúc / điều được và không được.
6. `kit/docs/agentflow/MODELS_PROPOSED.md` — catalog, usage, nâng cấp năng lực.
7. `kit/docs/agentflow/OPEN_DECISIONS.md` — danh sách những quyết định cần cùng nhau chốt.
8. `kit/docs/agentflow/ACCEPTANCE_TESTS.md` — checklist kiểm thử trên macOS thật.

## Tự kiểm tra trong môi trường thử nghiệm

```bash
python3 -m unittest discover -s tests -v
```

**Tài liệu tham khảo:**
- Codex hooks: https://learn.chatgpt.com/docs/hooks
- Claude Code hooks: https://code.claude.com/docs/en/hooks
- Claude Desktop: https://code.claude.com/docs/en/desktop

### Ma trận mức đáp ứng

Xem [`kit/docs/agentflow/STATUS_MATRIX.md`](kit/docs/agentflow/STATUS_MATRIX.md) để biết chính xác phần **đã triển khai/đã unit-test**, phần **chưa kiểm tra trên macOS GUI** và phần **logic đang để đề xuất**.
