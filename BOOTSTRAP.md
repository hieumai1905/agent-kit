# Setup v1.1.0-slim-candidate.2

> Bản thử đã qua sàng lọc code, chưa xác nhận hiệu quả tổng quát hoặc UI thật. Chỉ setup/nâng cấp khi người dùng chủ động yêu cầu trong đúng chat; phát hành trên Git không tự cập nhật phiên đang chạy. Luồng thường xem docs/SLIM.md.

Chỉ áp dụng khi người dùng yêu cầu setup. Cài workflow không phê duyệt task code hoặc tạo delegation. Đây là bản thử để kiểm thử thực tế; giữ nguyên tag và clone cũ để rollback.

## Clone đúng bản và đúng đích

1. Chốt `TARGET_CWD` bằng `pwd -P` trước clone/cd. Đối chiếu Git root. Nếu root ở cha, nhiều repo hoặc chưa có Git thì làm rõ đích; không nâng root, cài hàng loạt hoặc `git init`. Đích không được là repo kit. Với yêu cầu nâng cấp một phiên đang làm, giữ đúng repo/state đã xác định trong phiên, không suy lại đích thành thư mục workspace cha.
2. Clone đúng tag ra ngoài mọi product tree, mặc định ~/.local/share/agent-workflow-kit/v1.1.0-slim-candidate.2:

```sh
git clone --branch v1.1.0-slim-candidate.2 --depth 1 https://github.com/hieumai1905/agent-kit.git /ABS/KIT
```

Đối chiếu origin, HEAD và commit thật của tag; SHA bắt buộc trong prompt hiện hành trên main phải khớp. Giữ lại SHA thực đã dùng. Nếu clone đã tồn tại, kiểm trạng thái trước khi dùng; không reset/pull đè, đổi main/latest hoặc ghi đè clone cũ. ZIP cần đối chiếu checksum được giao và manifest; manifest chỉ kiểm toàn vẹn, không xác thực nhà phát hành. /ABS/KIT và /ABS/PROJECT là canonical paths đã chốt.

Với chat đang làm việc, nâng cấp tại điểm dừng an toàn: giữ test/process và output; checkpoint phần đang làm khi cần, ghi baseline source/HEAD/index trước setup. Không đổi workflow giữa đợt patch hoặc tự hủy test để cài kit.

3. Cần Git và Python 3.11+. Chạy verify_release.py và `python3 -B /ABS/KIT/tools/agentflow.py --repo /ABS/PROJECT version`: manifest PASS, version 1.1.0-slim-candidate.2. Đọc RELEASE.json, README và hướng dẫn liên quan. Không tự cài dependencies, đổi auth/model/settings. Smoke report sinh trong kit ngoài project, không thay runtime/policy.

## Nâng cấp và áp dụng

4. Đọc chỉ dẫn đang hiệu lực cùng override. Tracked/mixed AGENTS.md/CLAUDE.md cần dừng, không tự untrack/unstage/skip-worktree. Nội dung ngoài managed block phải được giữ nguyên; chỉ khai báo `guidance_classification` KIT_ONLY khi đã kiểm tra nó thực sự là quy tắc vận hành kit. Block tùy biến không được overwrite. Xem payload trong docs/USAGE.md khi cần.
5. Giữ state-home và task/history đang có khi nâng cấp; mặc định state ngoài repo. Không tạo state mới để che lỗi. Preview rồi apply cùng tham số:

```sh
python3 -B /ABS/KIT/tools/agentflow.py --repo /ABS/PROJECT setup --mode advisory --upgrade
python3 -B /ABS/KIT/tools/agentflow.py --repo /ABS/PROJECT setup --mode advisory --upgrade --apply
```

Truyền cùng `--state-home /ABS/STATE` cho mọi lệnh nếu phiên đã dùng vị trí riêng; giữ `AGENTFLOW_STATE_HOME` nếu có. Với H/D đã chọn trước, giữ `--delegated-advisory`; setup không tạo/gia hạn H/D. Một writer, direct approval mặc định.

6. Setup tạo backup, guidance, inventory ngoài repo và Git local exclude đúng root paths. Không sửa product .gitignore/hooks/global config/index. Partial failure phải báo BLOCKED, transaction/backup và hiện trạng, không rollback mù hoặc báo READY. Chỉ dựng guidance/metadata; không sửa source sản phẩm trong setup.
7. Đọc lại AGENTS.md và CLAUDE.md sau cài, kiểm mode/helper/version/đích/state, nội dung riêng và chỉ dẫn ưu tiên. SETUP_LOCAL_READY chưa tự xác nhận provider nạp hướng dẫn. Đọc chi tiết được tham chiếu theo nhu cầu.
8. Kiểm doctor, `artifacts inventory`, `artifacts check`, baseline source/HEAD/index và backup. Doctor exit 0 chưa đủ: đọc JSON state healthy và guidance đều ADVISORY, không LEGACY_OR_CUSTOM. Source ngoài guidance, HEAD và staged index phải giữ nguyên. Untracked status có thể giảm vì local exclude, không phải xóa file. Không kiểm được/truncated thì dừng READY.
9. Chỉ báo SETUP_READY khi đã quan sát: đích; checksum/version; mode; readback hai guidance và việc áp dụng trong chat; state/backup transaction; inventory/exclude/staged check; bảo toàn source/index/HEAD. Nếu session chưa áp dụng được thì NEEDS_SESSION_REFRESH; conflict thì BLOCKED cùng nguyên nhân cụ thể. Sau nâng cấp, resume công việc đang có, đối chiếu nguồn/contract và quyết định hiện tại; không tạo lại task hoặc suy quyền mới từ state. Legacy nhiều repo thiếu footprint sẽ là INCOMPLETE/UNKNOWN; phải khai báo/duyệt revision mới và chạy test phù hợp, không tự nâng bằng chứng cũ.

## File kit và rollback

Artifact mới chỉ phục vụ kit phải nằm ngoài product tree và được đăng ký; cập nhật inventory/fingerprint sau ghi. Checker đọc current contents dưới các runtime roots đã đăng ký; giữ root hẹp để kiểm có giới hạn. `artifacts check --data -` nhận product_paths để đối chiếu INDEX với scope. Path kit đã biết, marker/state vẫn chặn; trùng nội dung chưa rõ nguồn cần phân loại cụ thể theo docs/USAGE.md, không whitelist extension. Kiểm trước handoff và trước/sau staging được duyệt riêng. Setup không stage/commit/push/deploy.

Local exclude tránh add nhầm thông thường; checker phải được agent gọi, không có hook cưỡng chế mọi commit. Bản sao đã biến đổi không giữ marker/hash cần review. Gỡ/rollback guidance bằng transaction của installer mới khi file chưa đổi; giữ state/history và clone cũ. Runtime cũ đọc DB được không đồng nghĩa nhận diện được guidance mới.
