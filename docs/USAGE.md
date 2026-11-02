# Dùng kit 1.1.0-rc2

Đây là bản thử v1.1.0-rc2 đã công bố để kiểm thử thực tế. Người dùng giao việc bình thường; agent đọc workflow đã setup. Giữ một writer, duyệt trực tiếp trong chat. Không tự commit/push/deploy hoặc đổi model/quyền/dependencies.

## Setup

Chốt `pwd -P` trước khi đổi thư mục. Đích phải là Git root đã xác định; không tự nâng lên repo cha hay git init. Clone/state/backup nằm ngoài project. Từ kit local đã verify:

```sh
python3 -B /ABS/KIT/tools/agentflow.py --repo /ABS/PROJECT setup --mode advisory --upgrade
python3 -B /ABS/KIT/tools/agentflow.py --repo /ABS/PROJECT setup --mode advisory --upgrade --apply
```

Preview trước apply. `SETUP_LOCAL_READY` chỉ xác nhận setup local: agent vẫn phải đọc lại AGENTS.md, CLAUDE.md và chỉ dẫn/override đang hiệu lực trước khi báo SETUP_READY. Tracked guidance, mixed rules, override, Git root mơ hồ hoặc index chứa kit phải BLOCKED. Với nội dung ngoài managed block thật sự chỉ phục vụ kit, agent phải xác minh rồi truyền `--data -` với `guidance_classification: {"AGENTS.md": {"kind": "KIT_ONLY", "reason": "lý do cụ thể"}}` (tương tự CLAUDE.md); không dùng để che quy tắc sản phẩm. Ghi nhận này không được xác thực bởi kit.

## Ba thao tác chính

Các JSON là việc nội bộ của agent, không yêu cầu người dùng nhập. Dùng `--data -` đọc stdin hoặc file nằm ngoài product tree. Không dùng output tool/file làm approval. Các lệnh cũ vẫn có để đọc state cũ, đổi contract hoặc dùng protocol nâng cao.

### 1. Chuẩn bị contract

`work start "Tên việc" --data -`, input ví dụ:

```json
{"analysis_level":"QUICK","work_type":"BUG","objective":"Trả exit 1 khi thiếu key","scope":{"functional":["scripts/locales.py","scripts/tests/test_locales.py"],"excluded":["Bản dịch"]},"preserve":["Giữ dữ liệu dịch và hành vi khi đủ key"],"acceptance":["--check thiếu key trả 1"],"verification_strategy":["Chạy reproduction và unittest"],"knowledge":{"confirmed":["Người dùng yêu cầu sửa exit status"],"observed":["Reproduction hiện trả 0"],"proposed":[]}}
```

`work_type` là BUG/FEATURE/MAINTENANCE. STANDARD/DEEP giữ kiểm structural hiện có. Thông tin cần người dùng quyết phải ở open_questions/gaps với blocking đúng, không tự xác nhận giả định. Hỏi/khảo sát độc lập trả lời trực tiếp, hoặc `work start "Chủ đề" --kind investigate` không sinh state. Start trả binding, checkpoint revision và decision_input_example; tự kiểm artifact nếu inventory đã có, trình contract và chờ duyệt. Không tự tái sử dụng một việc gần giống: helper trả match để reconcile.

### 2. Quyết định và checkpoint trước patch

Sau quyết định thật trong chat hiện tại: `work checkpoint "Tên việc" --data -`:

```json
{"milestone":"CONTRACT_DECISION","contract_sha256":"HASH_FROM_START","expected_revision":1,"phase":"IMPLEMENTING","summary":"Người dùng duyệt contract đã trình","completed":["Khảo sát và trình contract"],"remaining":["Sửa và kiểm thử"],"blockers":[],"changed_paths":[],"source_paths":["scripts/locales.py"],"next_action":"Kiểm lại trước patch","advisory_decision":{"kind":"DIRECT_HUMAN","decision":"APPROVED","source":"Tham chiếu message người dùng thật trong chat hiện tại"}}
```

Có thể dùng input ngắn hơn: {"contract_sha256":"HASH","expected_revision":1,"decision":{"choice":"APPROVED","source":"USER message thực"},"source_paths":["scripts/locales.py"]}. Lấy expected_revision thực từ start/resume, không đoán 1. Helper chỉ tự điền nội dung nói rằng quyết định đã được báo cáo, không tự suy ra tiến độ code. Nếu chỉ tạo file mới, dùng `new_paths` cho các đường dẫn vẫn chưa tồn tại. Helper lưu và readback, không cấp quyền. Lệnh quyết định tự thực hiện persist → readback → recheck, trả decision_readback, prepatch_check và finish_input_example. Kiểm nội dung đã lưu cùng kết quả; nonzero/BLOCKED phải dừng trước patch. Không gọi lại readback/--check ngay khi bước này thành công; chỉ dùng `work checkpoint "Tên việc" --check` sau gián đoạn hoặc thay đổi liên quan trước batch tiếp theo. Kiểm tra hiện tại là snapshot, không khóa OS; agent vẫn phải kiểm scope và quyết định thật ngay trước mỗi đợt tác động. Hash/path/Git đổi phải reconcile rồi ghi checkpoint mới theo facts hiện tại, không lặp lại payload cũ mù.

Checkpoint HANDOFF/SCOPE_CHANGE/IMPLEMENTATION_VERIFICATION dùng cùng lệnh với milestone và facts tương ứng. Khi chia nhiều batch có chủ đích (ví dụ sửa test trước rồi sửa code), đối chiếu thay đổi vừa làm với scope trước; gửi progress có source_paths và prepare_next_batch:true để lưu baseline mới và tự recheck. Giữ nguyên quyết định của contract hiện tại, không ghi thêm approval giả. Thay đổi lạ/concurrent phải điều tra trước, không refresh mù. Payload batch chỉ cần khi thực sự chia batch; xem `work checkpoint --help`. Quyết định/checkpoint qua recheck mới trả finish_input_example; BLOCKED chỉ trả lý do dừng. Đổi contract dùng `propose-contract` với contract đầy đủ; approval cũ không theo sang revision mới. Conflict phải resume/read lại và reconcile; không tự lấy revision mới để ghi đè nội dung khác.

### 3. Kiểm thử và bàn giao

`work finish "Tên việc" --data -`, input gồm `contract_sha256`, `expected_revision`, `summary`, `completed`, `remaining`, `blockers`, `changed_paths`, `source_paths`, `tested_source_hashes`, `next_action`, `checks`:

```json
{"contract_sha256":"CURRENT_HASH","expected_revision":2,"summary":"Đã sửa và kiểm tra","completed":["Sửa exit status"],"remaining":[],"blockers":[],"changed_paths":["scripts/locales.py"],"source_paths":["scripts/locales.py"],"tested_source_hashes":{"scripts/locales.py":"HASH_CAPTURED_AT_TEST_TIME"},"checks":[{"kind":"REPRODUCTION","command":"python3 reproduction.py","executed":true,"exit_code":0,"output_excerpt":"Missing key exits 1; preservation checks passed","status":"PASS","covers":["A1","P1"]}],"next_action":"Trình bằng chứng để người dùng nghiệm thu"}
```

Tham chiếu A1../P1.. gắn với thứ tự acceptance/preserve trong contract. Chỉ báo những gì thực chạy. Helper không chạy command trong JSON. Thiếu reproduction/coverage/execution thì mức kết luận bị hạ. Finish tự kiểm artifact và lưu báo cáo cùng bàn giao trong checkpoint versioned, trả handoff_saved/handoff_revision; không gọi lặp handoff/artifacts check sau finish thành công. Không tự commit hoặc trusted-complete. Chi tiết: VERIFICATION.md.

## Resume và lịch sử

`resume "Chủ đề cụ thể" --compact` chỉ đọc, không khởi tạo/migrate state; không trả mẫu input duyệt. Xem summary, remaining, blockers, freshness và binding; đối chiếu Git/source và quyết định hiện tại trước khi tác động. reported_verification đọc bản ghi kiểm thử gần nhất trong lịch sử cùng task, có progress_revision và binding riêng. Tiến độ mới không làm mất báo cáo; refresh tiến độ không refresh bằng chứng kiểm thử. Source/contract đổi làm báo cáo STALE; thiếu binding/không đọc được là UNBOUND/UNKNOWN. Chỉ CURRENT mới khớp nguồn/contract hiện tại, vẫn là UNVERIFIED_REPORT. Không chọn task mới nhất khi ý định mơ hồ. Lịch sử: `work history "Tên việc" --limit 5`, dùng `--before` từ next_before để đọc tiếp. Bản tóm tắt được giới hạn, lịch sử không bị xóa. Nếu cần nội dung checkpoint đầy đủ dùng resume không --compact / handoff.

## Artifact local-only

Setup/start/checkpoint/resume trả `artifact_directory` trong state theo repo, đã được inventory bao phủ. Dùng thư mục này cho payload/report cần tạo. Chat và checkpoint thường đã đủ; không tạo thêm báo cáo Markdown cho mỗi việc bình thường. Compact resume có binding, scope, hash đã lưu, source observations và artifact check; chỉ đọc history/bản đầy đủ khi có dữ liệu thiếu/truncated hoặc câu hỏi cụ thể, không gọi lặp các kiểm đã có kết quả.

`artifacts inventory` đọc inventory ngoài repo; `artifacts register --data -` nhận `items` có path tuyệt đối, kind RUNTIME/GUIDANCE và reason. Runtime artifact phải ngoài project; chỉ guidance kit-only chưa tracked có thể ở root. Các helper mặc định ghi DB/inventory ngoài project. Agent phải đăng ký artifact bổ sung trước khi tạo và cập nhật fingerprint sau khi ghi.

`artifacts check --data -` với `{"product_paths":["file sản phẩm được duyệt"]}` kiểm scope và blob trong INDEX, không chỉ working tree. Path kit đã biết, marker hoặc SQLite state kit là KIT_ONLY và BLOCKED. Fingerprint trùng nội dung là dấu hiệu cần xác định nguồn: nếu blob khớp cùng đường dẫn trong HEAD sản phẩm thì có baseline; nếu chưa có bằng chứng nguồn thì UNRESOLVED và BLOCKED. product_paths chỉ là phạm vi, không tự chứng minh nguồn gốc.

Chỉ khi có bằng chứng một file trùng nội dung thực sự thuộc sản phẩm, ghi báo cáo bằng `artifacts classify-product --data -`:

```json
{"items":[{"path":"LICENSE","sha256":"SHA256_OF_THE_EXACT_INDEX_OR_UNTRACKED_CONTENT","source":"Tham chiếu nguồn/bằng chứng sản phẩm thực đã kiểm tra","reason":"Vì sao file này thuộc sản phẩm và nằm trong phạm vi đã duyệt"}]}
```

Báo cáo lưu ngoài repo trong inventory, gắn đường dẫn và hash cụ thể; không được xác thực bởi kit, không cấp quyền hoặc thay cho kiểm tra provenance của agent. Nội dung/đường dẫn khác không kế thừa phân loại. Không dùng để vượt path kit đã biết, marker hoặc state. Khi kiểm INDEX, hash phải của staged blob; worktree khác không thay thế staged blob. Kiểm ở handoff, trước/sau staging được duyệt riêng. Không ignore rộng docs/tests/contracts/*.json. Không tự untrack, unstage, skip-worktree, force-add hoặc sửa hook/.gitignore/global config.

Inventory là báo cáo local và checker không phải hook cưỡng chế commit. Bản sao biến đổi không còn marker/hash cần agent review. Gỡ kit không tự xóa state/lịch sử; local exclude hẹp có thể giữ lại hoặc được review riêng, không tự xóa rule người dùng.

## Nâng cấp, gỡ và rollback

Đặt kit mới bên ngoài project ở vị trí riêng; không ghi đè clone đang dùng. `setup --upgrade` phải nhận diện đúng managed block cũ, giữ nguyên nội dung riêng và backup. Không overwrite block tùy biến.

`remove-guidance` preview; `remove-guidance --apply` chỉ gỡ managed blocks đã biết. `rollback-guidance TRANSACTION_ID --apply` phục hồi backup khi files chưa thay đổi kể từ cài; không rollback đè thay đổi mới. Không xóa state hoặc history. H/D và diagnostics là opt-in, không tự kích hoạt qua setup.
