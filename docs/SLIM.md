# Slim candidate — limited prerelease

Version `1.1.0-slim-candidate.2`. Setup/upgrade only at the user's explicit request in that session; publication does not update existing sessions. Code screening passed two historical tasks; repeated efficiency confirmation and actual UI acceptance remain incomplete. Do not claim general usage/cost savings.

Keep the approved outcome small and concrete. Read relevant code/data first; present one example that must change and one that must stay the same. Reuse actual USER approval once. Analysis/proposals need no records. This is an advisory process, not OS enforcement or authenticated approval.

After approval, use your installed helper prefix followed by these three milestones. Use explicit paths including product regression tests. The helper handles task IDs, revisions, decision persistence/readback, source snapshots, command logs and the saved handoff.

```sh
HELPER work begin "Missing-key exit status" \
  --source-ref "Current USER message approving this exact task" \
  --objective "Missing keys return failure; complete translations still pass" \
  --path scripts/locales.py --path scripts/tests/test_locales.py \
  --accept "A missing translation key returns exit code 1" \
  --preserve "Complete translations keep exit code 0 and files stay unchanged" \
  --test 'python3 -B -m unittest discover -s scripts/tests -p test_locales.py' \
  --covers A1,P1
HELPER work verify /RETURNED/begin-receipt.json
HELPER work handoff /RETURNED/verification-receipt.json \
  --summary "Describe actual behavior and evidence" --remaining "Any untested requirement"
```

`HELPER` denotes the complete prefix printed in AGENTS.md, not a new executable or a variable to write inside the project. Inspect begin's decision source and prepatch check before patching. BLOCKED/nonzero means stop. Do not repeat a successful immediate check. Every returned receipt is external; use the latest one. No IDs/hashes need copying. An old receipt, changed contract/progress, changed index/HEAD, changed read-only input, or change outside declared files requires reconciliation. Existing task titles never silently gain approval.

`--covers` is your reported mapping to acceptance A1.. and preservation P1.., not proof that the command checks those semantics. Omitting it leaves coverage incomplete. `--scenario` records a real interaction path; command checks alone leave actual UI workflow unverified. Distinguish backend fixtures from actual browser use. No automatic ready-for-users claim follows from passing tests.

For multiple check commands, use `work begin TITLE --data -` with one JSON object:

```json
{
  "contract": {
    "analysis_level": "QUICK", "work_type": "BUG",
    "objective": "The approved observable behavior",
    "scope": {"functional": ["app.py", "test_app.py"]},
    "acceptance": ["Concrete must-change case"],
    "preserve": ["Concrete must-preserve case"],
    "verification_strategy": ["Original reproduction and relevant regression suite"],
    "repositories": [{"key": "project", "root": "/ABS/GIT_ROOT", "write_paths": ["app.py", "test_app.py"], "read_paths": []}]
  },
  "approval_source": "Actual current USER approval reference",
  "checks": [{"argv": ["python3", "-B", "-m", "unittest"], "kind": "REPRODUCTION", "covers": ["A1", "P1"]}]
}
```

Commands run **without a shell**, in the project, with current process permissions/environment. Existing environment variables in argv (such as `$EVAL_PYTHON`) expand without shell evaluation. No package installation or provider call is introduced by this helper. Project tests themselves are executable code and are not sandboxed by the kit. Declare trusted, approved project commands. Timeout defaults to 300 seconds per command (configurable 1–600); failures/timeouts/missing executables return nonzero and remain failed in handoff. Raw logs are external and bound by digest. Changing sources during/after tests invalidates the evidence.

This default path is for one approved implementation batch in one Git root. If you need another intentional patch batch, a technical scope refinement, multiple roots, migration, security/permissions, billing, delegation or long handoff, use the existing `work checkpoint`/`work sources`/`work finish` and [USAGE.md](USAGE.md); keep the same approval only while its actual scope still applies. Do not erase or recreate a task to bypass a conflict. Existing advanced APIs and old state/history are retained unchanged.

Working baselines cover Git-visible tracked and untracked files, logical index entries and HEAD. They preserve preexisting changes without claiming to monitor every ignored file or concurrent edit between observations. Receipts/SQLite are same-user reports, not signatures or grants. All kit-only artifacts stay under the external artifact directory; begin/handoff retain the existing inventory/INDEX check. Do not add operational files to the product repo, force-add ignored guidance, unstage/untrack files or publish automatically.
