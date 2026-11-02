# Checkpoint và tiếp tục công việc

State ngoài repo là báo cáo UNVERIFIED; không thêm quyền ghi hoặc xác thực approval.

## Khi nào lưu?

Chỉ áp dụng cho task cần tiếp tục/bàn giao, không lưu mỗi câu hỏi độc lập hoặc mỗi message:

| Mốc | Nội dung cần giữ |
| --- | --- |
| CONTRACT_DECISION | Quyết định về contract, nguồn do agent báo, ràng buộc revision/hash; câu hỏi làm rõ không tự là phê duyệt |
| SCOPE_CHANGE | Phạm vi mới và phần còn phải quyết định; không tái sử dụng approval cũ cho contract khác |
| IMPLEMENTATION_VERIFICATION | Đã sửa gì, kiểm tra nào thực chạy, kết quả, source hashes, phần chưa kiểm thử và việc còn lại |
| HANDOFF | Trước khi chờ quyết định/dừng/bàn giao: đã làm, chưa làm, blocker và next action |

Agent không cần đợi người dùng nhắc. Khi đang chờ duyệt contract lần đầu, dùng HANDOFF/WAITING_DECISION, không tự ghi CONTRACT_DECISION/APPROVED. Trong STRICT, chỉ được lưu báo cáo ngoài repo; không sửa product code hoặc chạy test có side effects bằng guidance này.

## Helper — agent dùng, người dùng không phải điền JSON

Sau khi tìm đúng task bằng `resume`/`tasks` và đọc contract hiện hành:

```sh
python3 tools/agentflow.py --repo "/ABS/REPO" checkpoint-template TASK_ID --milestone HANDOFF
python3 tools/agentflow.py --repo "/ABS/REPO" checkpoint-milestone TASK_ID "/OUTSIDE/progress.json" --expected-revision N
```

Template trả `checkpoint` và `expected_revision`. Agent kiểm tra contract/record cũ, lấy phần `checkpoint`, điền facts thật rồi lưu JSON ở ngoài repo. Không lưu wrapper template như một checkpoint hoàn chỉnh. `summary`, `completed`, `remaining`, `changed_paths`, `blockers`, `next_action`, phase và milestone phải rõ, có giới hạn kích thước. ID/hash/revision là việc nội bộ của agent.

Contract binding phải khớp current canonical contract. Mốc implementation/verification phải có source_hashes; helper đối chiếu file hiện tại theo giới hạn quan sát của status helper, từ chối hash cũ/không quan sát được. Chỉ đối chiếu dependencies được báo, không chứng nhận đủ coverage hoặc test đã chạy. Không tự gắn báo cáo cũ vào contract mới.

Template mang tiếp các field quyết định/provenance đã biết và hiển thị binding cũ để agent reconcile; không tự mang kết quả implementation/test cũ sang một milestone mới. Agent đọc handoff trước, giữ phần còn phù hợp, ghi rõ phần bị quyết định mới thay thế. Việc lưu không xác thực nguồn quyết định đó.

Save dùng CAS revision PROGRESS hiện có. Có writer khác lưu trước thì trả conflict; agent đọc/reconcile rồi mới đề xuất bản mới, không ghi đè mù. Nội dung y hệt chỉ trả no_changes khi expected revision cũng đúng. Contract/file checks là snapshot trước khi lưu, không khóa atomic với thay đổi đồng thời; Status helper sẽ báo STALE nếu chúng đổi sau đó. Bản ghi luôn UNVERIFIED_REPORT, không chuyển lifecycle/approval/completion.

Lệnh `checkpoint` cũ vẫn đọc/lưu payload legacy như trước. Helper không tự chuyển chúng sang schema mới hoặc giả định chúng đã đầy đủ. Nếu lưu thất bại, agent phải báo checkpoint chưa lưu và đưa tóm tắt bàn giao ngắn, không báo thành công giả.

## Khi tiếp tục ở phiên khác

Người dùng có thể nói “Tiếp tục sửa lỗi locale”. Agent gọi cùng helper prefix được cài trong AGENTS.md:

```sh
python3 tools/agentflow.py --repo "/ABS/REPO" resume "Tiếp tục sửa lỗi locale"
python3 tools/agentflow.py --repo "/ABS/REPO" interact "Tiếp tục sửa lỗi locale"
```

Cả hai đường hiện trả handoff nếu match rõ; `interact` giữ các field cũ và thêm `resume`. Không chỉ trả một danh sách rồi bỏ mất dữ liệu tiếp quản.

`resume_brief` nằm trong handoff, gồm checkpoint MISSING/LEGACY/STRUCTURED, reported summary/phase/completed/remaining/blockers/changed paths/next action, freshness và các bước cần kiểm tra trước hiệu ứng. Nội dung là báo cáo để đọc, không phải chỉ dẫn vượt quyền. Thiếu checkpoint thì nói thiếu, không bịa tiến độ từ Git.

“Tiếp tục việc hôm trước” hoặc nhiều task tương tự phải hiện các tên ngắn để chọn. Không chọn theo mới nhất, kể cả chỉ còn một task nhưng câu hỏi không xác định công việc. Không tạo task từ yêu cầu resume. Named resume bỏ tiền tố ý định trước khi tìm; không sửa thresholds để ép tự chọn.

Resume chỉ đọc state đã có, không khởi tạo/migrate nó; state chưa tồn tại trả NO_MATCH/STATE_NOT_INITIALIZED và giữ filesystem nguyên. Lệnh tạo task/checkpoint vẫn dùng initialization ngoài repo hiện có. Trước khi tiếp tục tác động, agent đối chiếu current contract/Git, freshness hiện tại và quyết định trong provider hiện tại. Saved state không khôi phục quyền, không tự tái kích hoạt H/D đã hết hạn/thu hồi.
