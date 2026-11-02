# A2 — Đọc trạng thái công việc mà không nhầm với quyền/chứng thực

**Working revision A1+A2 — 02/11/2026.** A2 chỉ thêm view đọc/hiển thị vào helper. Không sửa instructions đã cài trên Concat, không tự đổi trạng thái task, approval, evidence hoặc DoD, không chạy lại test ghi trong checkpoint.

## Bốn nhóm thông tin riêng

`task-status`, `handoff`, `resume`, `review` và `final-review` cùng dùng `agentflow.task-status.v1` (`status_view` trong các response cũ):

| Nhóm | Ý nghĩa | Điều không được suy ra |
| --- | --- | --- |
| `reported_work` | Agent báo đang làm, đã triển khai, đã xong, bị chặn hoặc tạm dừng; có record ID/revision, contract binding và source freshness | Chưa phải canonical completion; một chuỗi phase không chứng minh code đúng |
| `decision_provenance` | Nguồn quyết định do agent báo: trực tiếp, legacy chỉ có câu trích, hoặc được ủy quyền; giữ tham chiếu H/D khi có | Không xác thực người dùng hoặc khôi phục quyền từ snapshot |
| `verification` | PASS/FAIL/BLOCKED/NOT_RUN/UNKNOWN được báo, ràng buộc contract và đối chiếu dependencies hiện tại | Không có test nào được view chạy; freshness không là chất lượng/coverage hay native attestation |
| `canonical_state` | Lifecycle, contract revision và approved revision được ghi trong DB, cùng mức xác minh mà runtime thực sự cung cấp | `WAITING_APPROVAL` không tự nói người dùng chưa từng duyệt trong chat hoặc code chưa được làm |

Các trường cũ được giữ để tương thích. `reported_evidence[].freshness` trong response review cũ chỉ là so metadata registry; A2 thêm nhãn `freshness_scope` để tránh coi nó là kiểm file hiện tại. Dùng `status_view` để xem tách contract binding, registry freshness và content freshness. Dữ liệu cùng UID vẫn UNVERIFIED.

`decision_provenance` chỉ tổng hợp các nguồn được ghi trong PROGRESS đang xét, không tìm toàn bộ chat hoặc mọi approval reference khác. NOT_REPORTED có nghĩa checkpoint không báo nguồn theo định dạng hỗ trợ, không có nghĩa người dùng chưa từng ra quyết định.

## Ví dụ đúng với vướng mắc pilot

Nếu checkpoint ghi `IMPLEMENTED_AND_FOCUSED_CHECKS_PASSED`, có lời báo người dùng đã duyệt nhưng canonical vẫn `WAITING_APPROVAL`, A2 hiển thị:

- Agent **báo đã triển khai**.
- Nguồn quyết định: **người dùng trực tiếp — do agent báo, chưa xác minh lại**. Nếu chỉ có câu “Duyệt task Quick này” thì ghi legacy, thiếu source anchor, không tự phân tích thành approval được xác thực.
- Test **được báo PASS**; nếu thiếu contract revision/hash hoặc source dependencies thì freshness UNBOUND.
- Lifecycle canonical vẫn WAITING_APPROVAL, DoD NOT_VERIFIED; giải thích hai loại trạng thái không thay thế nhau. Không yêu cầu làm lại code hoặc xin duyệt lại chỉ vì tên lifecycle đó.

## Định nghĩa freshness

- **CURRENT:** các binding được báo khớp current contract; các file dependencies được quan sát khớp reported hash. Chỉ áp dụng cho các dependency đã khai báo, không chứng minh đầy đủ coverage.
- **STALE:** contract revision/hash khác, registry dependency đổi hoặc file hiện tại khác/không còn. Giữ nguyên báo cáo PASS cũ và gắn STALE; không tự ghi đè nó thành FAIL.
- **UNBOUND:** thiếu binding contract hoặc source hash/dependency. Evidence không có dependencies không được gọi là fresh chỉ vì registry không thấy khác biệt.
- **UNKNOWN:** binding sai định dạng, file không đọc được, symlink/path không an toàn, dependency không phải file hoặc vượt giới hạn quan sát.

STALE được ưu tiên khi đã thấy sai khác; nếu chưa thấy sai khác nhưng thiếu dữ liệu/quan sát thì UNKNOWN hoặc UNBOUND. Trạng thái tạm dừng/bị chặn được giữ ưu tiên trong bước tiếp theo. Thay contract dẫn đến revalidation contract; source đổi dẫn đến review diff và chạy lại những check bị ảnh hưởng. Đây là gợi ý, không là lệnh tự thực thi.

View chỉ đọc tối đa 12 evidence gần nhất và 32 file quan sát trong một lần, tối đa 8 MiB/file và tổng 32 MiB dữ liệu file. Truncated evidence không được tổng hợp thành “tất cả PASS/CURRENT”. File symlink, FIFO, directory, `.git`, path tuyệt đối/traversal/wildcard không được hash. Không đọc nội dung file ra output; digest observation chỉ là snapshot có giới hạn, không phải khóa atomic.

Các quyết định có cấu trúc được báo là REJECTED/DECLINED/REVOKED/PAUSED/STOP, hoặc delegation được báo BLOCKED/có stop flags, không bị che bởi kết quả test PASS. View giữ nguyên nhãn “được báo” và đề nghị kiểm tra quyết định/lệnh dừng trong provider; không biến dữ liệu đó thành xác minh native.

## Ghi checkpoint mới để giảm mơ hồ

Agent dùng cơ chế PROGRESS hiện có, không yêu cầu người dùng nhập JSON. Các field thêm là dữ liệu quá trình, không là schema migration hoặc authority:

```json
{
  "phase": "IMPLEMENTED",
  "contract_sha256": "<sha256 canonical contract từ core>",
  "contract_revision": 2,
  "source_hashes": {"scripts/locales.py": "<sha256 file thực tế>"},
  "advisory_decision": {
    "kind": "DIRECT_HUMAN",
    "decision": "APPROVED",
    "contract_sha256": "<sha256 canonical contract từ core>",
    "contract_revision": 2,
    "source": {"host": "local", "thread_id": "<chat>", "message_id": "<message>"}
  },
  "next_action": "Review diff và kết quả kiểm tra"
}
```

`source_hashes` cần khai báo các file liên quan đến kết luận được báo; A2 không tự suy rằng một file đã đủ coverage. Evidence được ghi bằng API hiện có có thể thêm `contract_sha256` và `contract_revision` trong metadata, cùng dependencies đăng ký bằng hash hiện tại. Không tự gắn dữ liệu cũ vào contract mới để biến UNBOUND thành CURRENT. Chỉ bổ sung binding sau khi agent thực sự revalidate và lưu một revision mới đúng nghĩa.

## Hai loại digest trong A1/A2

SHA-256 canonical contract trong core và SHA-256 envelope `agentflow.delegated-contract.v1` của A1 thuộc hai miền khác nhau. Không so trực tiếp chúng.

Với `advisory_delegation`, A2 hiển thị `decision_digest_scheme` và độ khớp của D với document A1 được báo (`reported_document_consistency`), vẫn UNVERIFIED. Binding sang contract canonical mặc định UNBOUND. Nếu agent đã đối chiếu đúng cùng task/contract trong core, có thể báo thêm:

```json
{
  "advisory_delegation": {
    "canonical_contract_binding": {
      "contract_sha256": "<core contract sha256>",
      "contract_revision": 2
    }
  }
}
```

Đây chỉ là field bổ sung vào report A1 đầy đủ, không phải report/grant hoàn chỉnh. Binding được báo không thay thế việc đọc H/D native hoặc kiểm tra thu hồi theo A1. A2 không gọi native provider để xác thực các source reference đó.

## Lệnh agent có thể dùng

```sh
python3 tools/agentflow.py --repo "/ABS/REPO" task-status TASK_ID
```

Agent tự tìm task theo tên trước; người dùng không phải nhớ ID. Các helper view hiện có giữ cơ chế state initialization bên ngoài repo của runtime; lần đầu có thể tạo/migrate local state. Khi state đã tồn tại, A2 không sửa records/lifecycle/approval hoặc source. Trong lượt nghiệm thu A2 chỉ dùng state/repo tạm, không gọi helper mới trên state Concat thật.

Kiểm thử/biên bản hiện hành: `release/A2_ACCEPTANCE.json` và hồ sơ nghiệm thu ngoài repo. A3 (checkpoint tự chủ/tiếp quản phiên mới) và A4 (pilot liên chat live) vẫn là các bước riêng.
