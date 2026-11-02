> **Mốc hiện hành v1.0 — 02/11/2026:** v1.0 chỉ nghiệm thu Codex local, một writer tuần tự. Bắt đầu ở 00_BAT_DAU_V1_0.md; hướng dẫn nhiều provider bên dưới là tham khảo chưa chứng nhận, không yêu cầu mở thêm pilot.

# HƯỚNG DẪN TÍCH HỢP VÀ QUẢN TRỊ KIT — D3–D7 PRACTICAL

**Ngày 29/10/2026** · Hướng dẫn dành cho repo thử hoặc repo làm việc sau khi hiểu rõ giới hạn quyền.

## 1. Mục tiêu và ranh giới

Bộ kit hỗ trợ quy trình coding trong Codex Desktop/CLI và Claude Desktop Code/CLI **qua các tệp hướng dẫn mà hai hệ sinh thái có thể đọc**. Không cài phần mềm/UI mới, không tự gọi provider, không cần subagent. Mỗi repo dùng một working tree; multiwriter chỉ được hỗ trợ như *quy tắc phối hợp*, **chưa phải cơ chế khóa cưỡng chế**.

`AGENTS.md` là điểm vào của Codex; `CLAUDE.md` là điểm vào của Claude. Mọi hướng dẫn chỉ là conventions. Khả năng đọc file tùy phiên bản/cách mở repo, cần kiểm tra thực tế trong từng app. Không khẳng định file này thay thế permissions/sandbox.

## 2. Yêu cầu tối thiểu

- Python 3.11+, `git` (nếu cần repo status); macOS là môi trường đích, nhưng tests trong gói chạy được trên Linux.
- Thư mục kit bền vững ở **ngoài** repo cần tích hợp. Chạy `python3 ...` từ thư mục kit.
- Không cần `sudo`, API key, quyền admin, cài extension/hook hoặc cấp quyền riêng trong bước hướng dẫn này.
- Backup thư mục `.git`/mã nguồn của repo theo quy trình riêng nếu thử trên dự án quan trọng. Tốt nhất thử trên repo giả trước.

## 3. Một lần cài vào repo

```sh
# 1. Kiểm tra kit
python3 tools/verify_release.py
# 2. Kiểm tra repo và tính năng hiện có
python3 tools/agentflow.py --repo "/ABS/REPO" doctor
# 3. Xem dự kiến thay đổi; CHƯA ghi
python3 tools/agentflow.py --repo "/ABS/REPO" install-guidance
# 4. Cài STRICT mặc định; chỉ ghi AGENTS.md + CLAUDE.md
python3 tools/agentflow.py --repo "/ABS/REPO" install-guidance --apply
```

Hãy xem `git diff -- AGENTS.md CLAUDE.md` sau cài. Installer gắn marker `AGENTFLOW_V3_GUIDANCE_ONLY`, giữ phần ngoài marker; nếu file có hardlink/symlink, managed block đã bị sửa hoặc không an toàn, installer từ chối. `--apply` luôn tường minh; các lệnh còn lại không áp dụng thay đổi vào repo.

### Hai chế độ

| Chế độ | Mục đích | Code writes từ kit |
|---|---|---|
| `strict` **mặc định** | Khảo sát, soạn Task Contract/plan/handoff, không sửa product code | Không có; fail-closed vì G2 chưa chứng nhận |
| `advisory` **tự chọn** | Làm coding sớm theo quy trình duyệt trong chat và permissions provider | Agent có thể sửa bằng **tool sẵn có** sau khi bạn duyệt; kit không cấp/enforce quyền |

`ADVISORY` không biến approval chat thành chứng thực native, không ngăn bypass ở cấp OS. Không nên dùng trong repo có rủi ro bảo mật cao, môi trường chứa secrets hoặc yêu cầu bắt buộc Strict Approval thực sự.

**Chuyển từ STRICT sang ADVISORY:**

```sh
python3 tools/agentflow.py --repo "/ABS/REPO" install-guidance --mode advisory --upgrade
python3 tools/agentflow.py --repo "/ABS/REPO" install-guidance --mode advisory --upgrade --apply
```

**Chuyển ngược về STRICT:** dùng `--mode strict --upgrade --apply` theo cách tương tự. Nếu repo chưa có marker, không cần `--upgrade`. Các file được giữ nguyên ngoài đoạn do kit quản lý.

## 4. Kiểm tra theo bốn bề mặt

Sau khi cài, mở **chính repo đó** bằng từng môi trường, yêu cầu agent:

> Hãy đọc hướng dẫn repo có liên quan. Chỉ rà soát read-only: tóm tắt quy trình giao task, mode hiện tại và giới hạn phê duyệt; không sửa file.

Đối với Codex Desktop và CLI, cần xác minh agent thực tế đọc `AGENTS.md`; đối với Claude Desktop Code và CLI, xác minh `CLAUDE.md` và tham chiếu `AGENTS.md` được dùng. **Đây là bước xác nhận hành vi bằng tay** chưa chạy được trong container Linux. Nếu ứng dụng không đọc file, không đoán là đã tích hợp. Nếu cần tích hợp sâu hơn, ưu tiên giải pháp của chính provider thay vì thêm một app quản lý riêng.

## 5. State và session

Tùy chọn `--state-home` để chuyển state ra nơi khác ngoài repo. Nếu bỏ qua, state dự kiến ở `~/Library/Application Support/AgentWorkflowV3`. Các SQLite task records không phải trust root; backup/restore cần quản lý riêng.

```sh
python3 tools/agentflow.py --repo "/ABS/REPO" tasks
python3 tools/agentflow.py --repo "/ABS/REPO" resume "tên công việc"
python3 tools/agentflow.py --repo "/ABS/REPO" repo-status
python3 tools/agentflow.py --repo "/ABS/REPO" final-review TASK_ID
```

Bạn không phải gõ Task ID khi giao việc thường ngày; agent có thể tự dùng ID từ state. Nếu nhiều task tương tự, cần hỏi chọn đúng task, không tự suy từ thời gian cập nhật.

## 6. Doctor, upgrade, rollback, uninstall

- `doctor`/`si-release-doctor`: kiểm tra state/capability và tình trạng repo, không cấp chứng nhận native.
- `install-guidance --mode ... --upgrade` là **dry-run** cho thay đổi chỉ dẫn. Phải thêm `--apply` để thực hiện; không tự merge managed block đã tùy chỉnh.
- `rollback-guidance TRANSACTION_ID --apply` phục hồi chính xác bản đã backup nếu hashes của hai file sau cài chưa đổi.
- `remove-guidance --apply` xóa các đoạn do kit quản lý, giữ nội dung riêng. Nếu tệp được tạo bởi kit và không còn nội dung khác, sẽ xóa tệp rỗng.

Backup được đặt ngoài repo và không chứng minh chống giả mạo nếu cùng UID với agent. Rollback/installer có kiểm tra thay đổi nhưng **không phải giao dịch nguyên tử trên hai file hoặc OS-enforced lock**.

## 7. Test sớm, không chờ dự án lớn

```sh
python3 tools/practical_smoke.py
python3 tools/release_acceptance.py
```

`practical_smoke.py` tạo repo tạm và state riêng, chạy 20 bước từ onboarding tới rollback và kiểm hash canary. Nó không sửa repo đang làm việc, không dùng model API/credits. Các bài native G2, multiwriter thực tế, GUI hooks, actual provider tool execution vẫn phải chứng minh riêng trước khi tuyên bố production-ready.

## 8. Không được tự mở rộng phạm vi

Không thêm SwiftUI, Control Panel, GUI/daemon, service, cloud backend, auto model switching, subagents, nhiều worktrees hay hàng chục tài liệu cho mỗi task. Nếu gặp nhu cầu chưa đáp ứng, ghi blocker, impact và đề xuất **phương án nhỏ nhất có thể thử được**; trình người dùng quyết định trước khi mở rộng.
