# Dùng kit 1.1.0-rc4

Đây là bản thử rc4 để kiểm thử thực tế. Người dùng giao việc bình thường; agent đọc workflow đã setup. Giữ một writer, duyệt trực tiếp trong chat. Không tự commit/push/deploy hoặc đổi model/quyền/dependencies.

## Setup

Chốt `pwd -P` trước khi đổi thư mục. Đích phải là Git root đã xác định; không tự nâng lên repo cha hay git init. Clone/state/backup nằm ngoài project. Từ kit local đã verify:

```sh
python3 -B /ABS/KIT/tools/agentflow.py --repo /ABS/PROJECT setup --mode advisory --upgrade
python3 -B /ABS/KIT/tools/agentflow.py --repo /ABS/PROJECT setup --mode advisory --upgrade --apply
```

Preview trước apply. `SETUP_LOCAL_READY` chỉ xác nhận setup local: agent vẫn phải đọc lại AGENTS.md, CLAUDE.md và chỉ dẫn/override đang hiệu lực trước khi báo SETUP_READY. Tracked guidance, mixed rules, override, Git root mơ hồ hoặc index chứa kit phải BLOCKED. Với nội dung ngoài managed block thật sự chỉ phục vụ kit, agent phải xác minh rồi truyền `--data -` với `guidance_classification: {"AGENTS.md": {"kind": "KIT_ONLY", "reason": "lý do cụ thể"}}` (tương tự CLAUDE.md); không dùng để che quy tắc sản phẩm. Ghi nhận này không được xác thực bởi kit.

## Ba thao tác chính

Các JSON là việc nội bộ của agent, không yêu cầu người dùng nhập. Dùng `--data -` đọc stdin hoặc file nằm ngoài product tree. Không dùng output tool/file làm approval. Các lệnh cũ vẫn có để đọc state cũ, đổi contract hoặc dùng protocol nâng cao.

Lượt chỉ khảo sát/đề xuất/contract chưa triển khai trả lời trong chat, không gọi helper mặc định. Sau quyết định triển khai, serialize đúng contract đã trình bằng start rồi lưu/readback/recheck quyết định bằng checkpoint trước patch. Không thêm policy/hành vi chưa được trình vào lúc ghi. Tracking bền vững được yêu cầu hoặc handoff của implementation đang làm vẫn dùng state. Start đã tìm việc hiện có và readback; không gọi lookup/resume lặp khi kết quả vừa trả đủ binding/revision.

### 1. Chuẩn bị contract

`work start "Tên việc" --data -`, input ví dụ:

```json
{"analysis_level":"QUICK","work_type":"BUG","objective":"Trả exit 1 khi thiếu key","scope":{"functional":["scripts/locales.py","scripts/tests/test_locales.py"],"excluded":["Bản dịch"]},"preserve":["Giữ dữ liệu dịch và hành vi khi đủ key"],"acceptance":["--check thiếu key trả 1"],"verification_strategy":["Chạy reproduction và unittest"],"knowledge":{"confirmed":["Người dùng yêu cầu sửa exit status"],"observed":["Reproduction hiện trả 0"],"proposed":[]}}
```

`work_type` là BUG/FEATURE/MAINTENANCE. STANDARD/DEEP giữ kiểm structural hiện có; xem `contract-template --level DEEP` khi cần hình dạng field. Routing xét objective, risk và scope thực: migration/auth/payment có thể yêu cầu DEEP; footprint rộng ít nhất STANDARD. Loại trừ/read-only/docs không tự tạo trigger. Thông tin cần người dùng quyết phải ở open_questions/gaps với blocking đúng, không tự xác nhận giả định. Hỏi/khảo sát độc lập trả lời trực tiếp, hoặc `work start "Chủ đề" --kind investigate` không sinh state. Start trả binding và checkpoint_revision; tự kiểm artifact nếu inventory đã có, trình contract và chờ duyệt. Không tự tái sử dụng một việc gần giống: helper trả match để reconcile.

Khi thay đổi tương tác, thêm `usage_scenario` là vài dòng mô tả dữ liệu đầu vào, hành động/thứ tự, phụ thuộc/thời gian chờ và kết quả; kiểm lưu/mở lại khi liên quan. Giả định có hậu quả cần khảo sát và nêu rõ trước khi chọn giải pháp. Không thêm worksheet hoặc giả vờ validator đã chứng minh hiểu đúng. Việc cơ học không cần trường này. Khi có usage_scenario, finish giữ trạng thái PARTIAL nếu chưa có báo cáo USER_WORKFLOW qua đường tương tác thực; xem VERIFICATION.md.

Nếu đã có usage_scenario và scope, helper tái sử dụng chúng cho scenarios/impact còn thiếu, ghi input_derivations và đánh dấu impact chỉ là inventory từ phạm vi khai báo, chưa xác thực dependency. Không bắt agent nhập lại cùng dữ kiện để qua khuôn STANDARD. Trường đã cung cấp nhưng sai không bị ghi đè; yêu cầu risk/evidence/challenge của DEEP vẫn phải đáp ứng riêng. Mọi nội dung được chuẩn hóa được lưu vào contract trước khi trình duyệt; chưa có phân tích ngữ nghĩa tự động.

CLI thường trả kết quả gọn; `--verbose` trả đầy đủ nếu chọn trước khi gọi. Không chạy lại mutation chỉ để xem chi tiết: dùng resume/handoff chỉ đọc. API Python vẫn trả dữ liệu đầy đủ. Ưu tiên CLI trực tiếp, kiểm mã thoát. Wrapper Python cần dùng `agentflow_runtime.client.run_checked(argv, data=payload)`: lỗi, timeout, JSON sai, BLOCKED hay readback sai phải kết thúc trước patch. Không dùng capture_output rồi bỏ returncode. Client không cưỡng chế caller cố tình bắt/bỏ lỗi, không là sandbox.

### 2. Quyết định và checkpoint trước patch

Sau quyết định thật trong chat hiện tại: `work checkpoint "Tên việc" --data -`:

```json
{"milestone":"CONTRACT_DECISION","contract_sha256":"HASH_FROM_START","expected_revision":1,"phase":"IMPLEMENTING","summary":"Người dùng duyệt contract đã trình","completed":["Khảo sát và trình contract"],"remaining":["Sửa và kiểm thử"],"blockers":[],"changed_paths":[],"source_paths":["scripts/locales.py"],"next_action":"Kiểm lại trước patch","advisory_decision":{"kind":"DIRECT_HUMAN","decision":"APPROVED","source":"Tham chiếu message người dùng thật trong chat hiện tại"}}
```

Có thể dùng input ngắn hơn: {"contract_sha256":"HASH","expected_revision":1,"decision":{"choice":"APPROVED","source":"USER message thực"},"source_paths":["scripts/locales.py"]}. Hoặc CLI trực tiếp:

```sh
python3 -B /ABS/KIT/tools/agentflow.py --repo /ABS/PROJECT work checkpoint "Tên việc" --decision APPROVED --source-ref "USER message thật" --expected-revision N --contract-sha256 HASH --source scripts/locales.py
```

Lấy revision thực từ start/resume, không đoán 1. Helper chỉ tự điền nội dung nói rằng quyết định đã được báo cáo, không tự suy ra tiến độ code. Nếu chỉ tạo file mới, dùng `new_paths` cho đường dẫn chưa tồn tại. Quyết định tự persist → readback → recheck, trả decision_readback/prepatch_check, không cấp quyền. Nonzero/BLOCKED phải dừng trước patch. Không gọi lại readback/--check ngay khi thành công; chỉ recheck sau gián đoạn/thay đổi trước batch tiếp theo. Hash/path/Git đổi phải reconcile rồi checkpoint facts mới, không lặp payload cũ mù. Đây là snapshot, không khóa OS.

Checkpoint chỉ nhận CONTRACT_DECISION/HANDOFF/SCOPE_CHANGE/IMPLEMENTATION_VERIFICATION, không có IMPLEMENTATION_PROGRESS. Tiến độ thường dùng HANDOFF/phase IMPLEMENTING. Khi chia nhiều batch có chủ đích, đối chiếu thay đổi vừa làm với scope trước; gửi progress có source_paths (legacy) và prepare_next_batch:true để lưu baseline mới và tự recheck. Giữ nguyên quyết định contract, không ghi approval giả. Thay đổi lạ/concurrent phải điều tra trước. Mẫu finish đầy đủ chỉ ở API/--verbose. Đổi contract dùng `propose-contract`; approval cũ không theo revision mới. Conflict phải đọc/reconcile, không tự lấy revision mới để ghi đè.

### 3. Kiểm thử và bàn giao

`work finish "Tên việc" --data -`, input gồm `contract_sha256`, `expected_revision`, `summary`, `completed`, `remaining`, `blockers`, `changed_paths`, `source_paths`, `tested_source_hashes`, `next_action`, `checks`:

```json
{"contract_sha256":"CURRENT_HASH","expected_revision":2,"summary":"Đã sửa và kiểm tra","completed":["Sửa exit status"],"remaining":[],"blockers":[],"changed_paths":["scripts/locales.py"],"source_paths":["scripts/locales.py"],"tested_source_hashes":{"scripts/locales.py":"HASH_CAPTURED_AT_TEST_TIME"},"checks":[{"kind":"REPRODUCTION","command":"python3 reproduction.py","executed":true,"exit_code":0,"output_excerpt":"Missing key exits 1; preservation checks passed","status":"PASS","covers":["A1","P1"]}],"next_action":"Trình bằng chứng để người dùng nghiệm thu"}
```

Tham chiếu A1../P1.. gắn với thứ tự acceptance/preserve trong contract. Chỉ báo những gì thực chạy. Helper không chạy command trong JSON. Thiếu reproduction/coverage/execution thì mức kết luận bị hạ. Finish tự kiểm artifact và lưu báo cáo cùng bàn giao trong checkpoint versioned, trả handoff_saved/handoff_revision; không gọi lặp handoff/artifacts check sau finish thành công. Không tự commit hoặc trusted-complete. Chi tiết: VERIFICATION.md.

### Nhiều repo / footprint rõ ràng

Thêm vào contract trước khi trình duyệt (root phải là Git root tuyệt đối, file tương đối cụ thể, không directory/glob/symlink):

```json
{"repositories":[{"key":"core","root":"/ABS/Core","write_paths":[],"read_paths":["contract/canvas.json"]},{"key":"frontend","root":"/ABS/Frontend","write_paths":["src/view.mjs","tests/view.test.mjs"],"read_paths":[]}]}
```

Tối đa 8 repo, 128 file, 64 MiB tổng và 8 MiB/file. File write chưa tồn tại được ghi null, không bị bỏ qua; read-only input thiếu phải chặn; việc xuất hiện/thay đổi ngoài baseline làm check stale. Decision/checkpoint tự chụp toàn bộ footprint, không trộn source_paths legacy. `changed_sources` là object repo key → danh sách write paths. Không dùng hash Core để đại diện frontend. Root khai báo không cấp quyền hoặc tự cài guidance vào repo khác.

Ngay trước test, chụp snapshot và giữ file bất biến:

```sh
python3 -B /ABS/KIT/tools/agentflow.py --repo /ABS/Core work sources "Tên việc" --output /RETURNED/artifact_directory/test-batch.json
```

Sau test, finish dùng `tested_sources_file` là đường dẫn trên thay source_paths/tested_source_hashes, và `changed_sources` repo key → file thực đã đổi. Các field/checks khác như ví dụ. `changed_paths` tương thích khi ánh xạ duy nhất vào write_paths, hoặc khớp đầy đủ changed_sources đã gửi; xung đột/đường dẫn mơ hồ bị từ chối, không đoán repo. Helper không tự chuyển changed_paths thành source_paths trong chế độ manifest. File snapshot phải ở artifact_directory; payload ngoài mọi product root. Snapshot không chạy test. Finish yêu cầu khớp đủ mọi file; thiếu repo/source đổi bị chặn. DECLARED_SCOPE_COMPLETE chỉ là footprint khai báo, không xác thực test hoặc mọi dependency. Legacy thiếu sibling hiện INCOMPLETE/UNKNOWN.

### Cập nhật file kỹ thuật trong phạm vi đã duyệt

Mặc định contract khóa đúng write_paths (EXACT). Người dùng khóa danh sách cụ thể thì giữ EXACT. Chỉ khi phạm vi được trình ban đầu cho phép bổ sung triển khai trong component/support file cụ thể, thêm policy vào contract trước duyệt:

Đối với yêu cầu theo chức năng/component, agent nên trình phạm vi bao gồm regression/support liên quan và policy hẹp ngay trong đề xuất đầu tiên. Không tự biến file dự kiến thành giới hạn mới của người dùng. Product regression tests nằm trong repo sản phẩm; payload/report của kit mới nằm trong artifact_directory.

```json
{"implementation_policy":{"mode":"SCOPED_REFINEMENTS","repositories":{"frontend":{"allow_under":["src/canvas","tests/canvas"],"support_files":["canvas-agent-contract.lock.json"]}}}}
```

Policy dùng repo key/root đã có; nêu allowance trong bản trình người dùng, không âm thầm tự bật sau approval. Chọn component đúng phạm vi, không mở toàn repo bằng dấu chấm. Tên thư mục không tự chứng minh phạm vi; ví dụ tests chỉ được dùng nếu phạm vi người dùng đã cho phép thật sự bao gồm nó. Tối đa 16 component, 32 support files/repo. File dependencies/config/migration/auth/security/payment được helper nhận diện không được thêm qua allowance; cần write_paths trong contract duyệt. Helper không chứng minh semantics: agent phải rà tác động/giới hạn thực trước mỗi refinement.

Giữ nguyên contract hash, gửi checkpoint (không propose-contract và không ghi một approval mới):

```json
{"contract_sha256":"UNCHANGED_APPROVED_CONTRACT_HASH","expected_revision":2,"implementation_plan":{"reason":"Bổ sung regression và manifest sinh cho đúng component đã duyệt","repositories":[{"key":"core","root":"/ABS/Core","write_paths":[],"read_paths":["contract/canvas.json"]},{"key":"frontend","root":"/ABS/Frontend","write_paths":["src/canvas/view.ts","tests/canvas/view.test.ts","canvas-agent-contract.lock.json"],"read_paths":[]}]}}
```

Dùng revision thực, đầy đủ roots/files của footprint hiện có cùng file bổ sung. Chỉ có repositories/reason trong input implementation_plan; các field contract không được nhét vào đây. Helper version plan trong PROGRESS cùng CAS, giữ quyết định gốc, bảo toàn facts trước đó, chụp/readback/recheck một lượt. Không tự cấp quyền hoặc tạo approval. Không được bỏ/downgrade file đã theo dõi, đổi root, ghi vào read-only input, thêm file ngoài policy. Contract/hành vi/acceptance/rủi ro thay đổi thì trình revision mới. Policy không có hoặc EXACT vẫn chặn file mới; không tự suy policy cho task cũ.

Refine trước patch/test, không khi finish. Work sources, checkpoint, finish và resume tự dùng footprint mới; snapshot cũ không được mở rộng theo. Báo cáo kiểm thử cũ giữ binding và có thể stale; chỉ chạy lại phần bị ảnh hưởng, không tự copy PASS hoặc lặp mọi suite chỉ để đổi metadata. State/contract cũ không bị migrate hoặc rewrite.

## Resume và lịch sử

`resume "Chủ đề cụ thể" --compact` chỉ đọc, không khởi tạo/migrate state; không trả mẫu input duyệt. Xem summary, remaining, blockers, freshness và binding; đối chiếu Git/source và quyết định hiện tại trước khi tác động. reported_verification đọc bản ghi kiểm thử gần nhất trong lịch sử cùng task, có progress_revision và binding riêng. Tiến độ mới không làm mất báo cáo; refresh tiến độ không refresh bằng chứng kiểm thử. Source/contract đổi làm báo cáo STALE; thiếu binding/không đọc được là UNBOUND/UNKNOWN. Chỉ CURRENT mới khớp nguồn/contract hiện tại, vẫn là UNVERIFIED_REPORT. Không chọn task mới nhất khi ý định mơ hồ. Lịch sử: `work history "Tên việc" --limit 5`, dùng `--before` từ next_before để đọc tiếp. Bản tóm tắt được giới hạn, lịch sử không bị xóa. Nếu cần nội dung checkpoint đầy đủ dùng resume không --compact / handoff.

## Artifact local-only

Setup/start/checkpoint/resume trả `artifact_directory` trong state theo repo, đã được inventory bao phủ. Dùng cho payload/report cần tạo. Product test worktrees/fixtures đặt ngoài các root inventory kit-only; lưu baseline dạng hash/patch, tránh copy nguyên code sản phẩm vào state rồi nhận nhầm provenance. Chat/checkpoint thường đã đủ; không tạo thêm Markdown mỗi việc. Compact resume có source observations/artifacts; source_hashes_summarized chỉ nói danh sách hash được rút gọn, không yêu cầu đọc full. Chỉ đọc thêm khi thiếu fact cụ thể/thực sự truncated/mơ hồ. Với process đang chạy, chờ output theo khoảng phù hợp (thường 30–50 giây), tránh vòng đọc log không đổi qua nhiều lượt model. Không lặp full suite nếu không có thay đổi/lỗi/nghi vấn mới.

Fingerprint scan đọc metadata có giới hạn và chỉ hash artifact cùng kích thước với blob ứng viên; nội dung khác kích thước không thể trùng byte. Giới hạn không đọc được/vượt budget vẫn BLOCKED; marker/path/state và bản sao cùng hash vẫn bị phát hiện.

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
