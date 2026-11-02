# Ủy quyền duyệt contract giữa hai chat — opt-in

Mặc định dùng duyệt trực tiếp. Chỉ dùng protocol này khi người dùng chọn rõ; cài đặt không tạo H/D.

## Ba quyết định riêng

1. Người dùng chọn cài protocol opt-in vào repo sau khi xem dry-run.
2. **H:** người dùng duyệt một đề xuất ủy quyền cụ thể trong chat điều phối. Quyền giao việc/review không mặc nhiên gồm quyền duyệt contract.
3. **D:** điều phối viên review rồi duyệt đúng contract hiện hành, trong giới hạn H.

H giới hạn một task Quick, một agent ghi tuần tự, cùng host `local`, tối đa hai giờ hoặc kết thúc task. Protocol chỉ hỗ trợ Codex có công cụ đọc transcript native; Claude dùng duyệt trực tiếp trong chat thực thi. Không ủy quyền tiếp. Commit/push/deploy, thao tác phá hủy, migrations, secrets/credentials/security và dependencies cần quyết định riêng của người dùng.

## Cài protocol — chỉ sau khi có quyết định cài riêng

Từ thư mục kit, trên repo thử đã được phép:

```sh
python3 tools/agentflow.py --repo "/ABS/REPO" install-guidance --mode advisory --delegated-advisory --upgrade
```

Kết quả chứa diff của từng file và `delegation_active=false`. Review diff, backup plan và instructions riêng trước khi thêm `--apply`. Nếu repo chưa cài kit thì không cần `--upgrade`. STRICT từ chối cờ ủy quyền. Lệnh không có `--delegated-advisory` khi nâng cấp là yêu cầu chuyển về luồng trực tiếp, không giữ cờ ngầm.

Installer chỉ cài managed blocks. Doctor hiển thị `OPT_IN_PROTOCOL_INSTALLED` và `NOT_ESTABLISHED_BY_INSTALLATION`, không chứng nhận có H/D. Mixed blocks bị báo không nhất quán. Gỡ và rollback dùng lệnh hiện có, kiểm tra byte/hash như trước; không sửa approval DB.

## Agent làm gì với H và D?

Trình H bằng tiếng Việt ngắn, gồm coordinator/executor host+chat, canonical repo/worktree, task, outcome/preserve/acceptance, file tương đối cụ thể, thao tác patch/test và thời hạn. Người dùng không cần điền JSON hay Task ID. Agent xử lý các mã phía sau và giữ tham chiếu đề xuất H cùng phản hồi gốc.

Agent thực thi trình contract, gồm `revision`, `objective`, `preserve`, `acceptance`, `files` và `verification_commands` (argv arrays). Điều phối viên chỉ duyệt sau review và đăng D dưới dạng **assistant message bình thường trong chat nguồn của chính mình**, ghi rõ task/revision/digest, repo/worktree, executor, files/actions. Tin nhắn gửi sang chat thực thi chỉ chứa tham chiếu tìm nguồn và hướng dẫn đối chiếu; nó không tự là approval.

Trước khi tiếp tục, agent thực thi độc lập dùng công cụ native để đọc userMessage chứa H và ngữ cảnh đề xuất, agentMessage chứa D và mọi thông điệp liên quan mới hơn ở cả hai chat. Dựa vào metadata do công cụ cung cấp, không dựa vào `role`/`verified=true` bên trong payload. Đọc đủ pagination đến mốc, không nhận nội dung truncated hoặc lịch sử thiếu. Nếu quyền truy cập/role/anchor thiếu hoặc quyết định mơ hồ thì dừng phần ghi và báo lý do.

Đối chiếu H/D với task, revision/digest và toàn bộ ràng buộc. Revision/digest đổi cần D mới. Vượt objective/preserve/acceptance, files hoặc verification của H cần người dùng đổi H; cùng file không đồng nghĩa vẫn cùng phạm vi. Files không dùng absolute/traversal/wildcard; kiểm symlink thực tế, Git và thay đổi chưa commit trước thao tác.

Đọc lại quyết định trước mỗi đợt ghi hoặc test có side effects; dữ liệu nguồn quá 30 giây cần refresh. Thu hồi/dừng/tạm dừng/hoàn tất/thay quyết định chặn tiếp tục. Người dùng dừng trực tiếp ở chat đích được ưu tiên. Resume phải xác minh lại, không kế thừa quyền từ snapshot. Read-then-write không atomic; không hứa thu hồi tức thời hay auto rollback.

## Helper: digest và bản ghi UNVERIFIED

```sh
python3 tools/agentflow.py --repo "/ABS/REPO" delegation-template
python3 tools/agentflow.py --repo "/ABS/REPO" delegation-contract "/OUTSIDE/contract.json"
python3 tools/agentflow.py --repo "/ABS/REPO" delegation-check "/OUTSIDE/report.json"
```

Các lệnh này không tạo state, không gọi model, không ghi repo và không chạy tests. Agent lưu output ở ngoài repo nếu cần. `delegation-contract` hash một envelope có `schema=agentflow.delegated-contract.v1` và `contract=<nội dung đầy đủ>`, JSON UTF-8 với keys sắp xếp, separators comma/colon, không NaN. Digest không chứng minh ai đã duyệt.

`delegation-template` cung cấp định dạng report cho agent. Các trường grant/decision/sources/observation phải được agent ghi từ quan sát thật, với thời gian epoch UTC. Nó không phải form người dùng điền. Các cờ `complete_context`, `enabled_by_human`, `explicit_decision` vẫn là **lời báo của agent**, không được biến thành bằng chứng xác thực.

`delegation-check` kiểm dữ liệu được báo: binding, thời hạn, revision/hash, scope, stop flags và snapshot đường dẫn/symlink. Nếu thiếu hoặc mâu thuẫn trả `DELEGATED_ADVISORY_BLOCKED` cùng blockers. Kể cả input giả nhưng hoàn toàn nhất quán, kết quả tốt nhất chỉ là **`SOURCE_REVIEW_REQUIRED`, `source_verification=UNVERIFIED`, `write_authorized=false`**. Exit 0 nghĩa diagnostic đã chạy, không phải phê duyệt task. Không có parser tự xác thực ý nghĩa lời người dùng hoặc native transcript adapter trong helper này; agent dùng công cụ provider để thực hiện bước đó theo protocol.

Sau khi tự đọc nguồn, agent có thể ghi nhận xét quá trình `DELEGATED_ADVISORY_ELIGIBLE` hoặc `DELEGATED_ADVISORY_BLOCKED`. Hai nhãn này vẫn là nhận xét UNVERIFIED, không là native receipt.

Dùng checkpoint hiện có, không thêm schema hoặc privileged status:

```json
{
  "phase": "DELEGATION_SOURCE_REVIEW",
  "advisory_delegation": {"schema": "agentflow.delegation-report.v1"},
  "next_action": "Nêu bước tiếp theo và các giới hạn"
}
```

Ví dụ trên chỉ minh họa vị trí field, không phải report hoàn chỉnh. Agent lấy report đầy đủ bằng `delegation-template`, rồi lưu qua `checkpoint TASK_ID progress.json --expected-revision N`; N là revision PROGRESS hiện có. Checkpoint luôn `UNVERIFIED_REPORT`, không đổi `approved`/trusted completion. State cùng UID vẫn có thể bị sửa, không dùng nó để cấp quyền khi resume.
