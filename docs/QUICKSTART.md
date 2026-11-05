# Compact kit v1.1.1: ordinary work

Use the installed helper prefix in AGENTS.md. Setup is explicit and separate from task approval. Identity comes from the provider environment; do not supply session IDs. No global setting, dependency, extra agent or publication is implied.

For a small authorized fix, use the short contract. A clear implementation request can supply authority; honor proposal-first/read-only instructions and exact locks. Do not ask again for an already authorized scope. Record its actual USER source without adding undisclosed permissions. Do not invent a usage_scenario or a heavy contract for a small CLI/library change. Critical risks and multiple repositories still require their existing checks. When genuinely needed, explain the user's decision using [DECISIONS.md](DECISIONS.md).

```sh
HELPER work begin "Missing key exit status" --source-ref "Actual USER approval" \
  --objective "Missing keys fail in check mode" --path locales.py --path test_locales.py \
  --accept "Missing keys with check return 1" --preserve "Complete data and noncheck keep 0; inputs unchanged" \
  --test 'python3 -B -m unittest -q' --covers A1,P1
```

`HELPER` is shorthand for the existing prefix, not a command/file to create. The response's `next_command` is an argv suffix to append to that prefix. Receipts can be short names resolved only inside this repo's external artifact directory. Inspect approval/prepatch before patching; then verify. TESTS_FAILED returns a retry command: read the relevant log, fill the actual repair summary, run retry before editing, verify again, then handoff with the actual outcome. Other BLOCKED/conflicts require reconciliation. Never replay a summary placeholder or switch APIs to bypass a block. Successful handoff already saves the report.

## Related files within the original scope

For component work, include a bounded file allowance in the initial authorized scope. Short begin flags `--allow-under src/component --allow-under tests/component` record future file allowances; use only permissions the actual request/decision covers. Known files use `--path`; `--support-file generated-manifest.json` also includes that known support file in the initial writable footprint. Protected dependency/security/config/migration files must be explicit `--path` files. With `--data`, use implementation_policy as shown in [USAGE.md](USAGE.md). Missing policy and exact USER file restrictions remain EXACT; do not retrofit an allowance into an old task.

Before editing a related additional file:

```sh
HELPER work refine RECEIPT --path tests/component/regression.py --reason "Related regression within the original component authority"
```

Inspect its prepatch result, then edit and verify with the new receipt. The original contract and USER decision stay fixed; the effective footprint gains the allowed file. Existing PASS is invalidated and all declared checks rerun. Same directory is not proof of semantic scope: new behavior, excluded effects or an exact USER lock need review. Refine rejects files already changed out of scope; it cannot authorize a patch retroactively. A real scope proposal stays separate from active authority; see [RECOVERY.md](RECOVERY.md).

## Choose evidence before approval

- CODE: declared code checks; no user journey was requested. This does not claim CLI/UI exercise.
- CLI: actual CLI behavior is required. Declare `verification_target: "CLI"`, `cli_entrypoint: "locales.py"` and include that file in repositories.write_paths/read_paths. Keep QUICK for a small scoped fix. A scenario alone does not raise risk.
- UI: declare `verification_target: "UI"` and the concrete usage_scenario; actual interaction evidence remains required. Unit/mock/CLI evidence cannot complete it. The advanced path records browser/provider evidence; command-only handoff leaves it pending.

For multiple checks, `work begin TITLE --data -` receives the approved object:

```json
{
  "contract": {
    "analysis_level":"QUICK", "work_type":"BUG",
    "objective":"Check mode reports missing translations with failure status",
    "scope":{"functional":["locales.py","test_locales.py"]},
    "acceptance":["Missing key in check mode returns 1"],
    "preserve":["Complete data returns 0 and JSON inputs stay unchanged"],
    "verification_target":"CLI", "cli_entrypoint":"locales.py",
    "repositories":[{"key":"project","root":"/ABS/PROJECT","write_paths":["locales.py","test_locales.py"],"read_paths":["data/en.json","data/vi.json"]}],
    "verification_strategy":["Existing regression and direct CLI reproduction"]
  },
  "approval_source":"Actual current USER approval of this scope",
  "checks":[
    {"argv":["python3","-B","-m","unittest","-q"],"kind":"REGRESSION","covers":["A1","P1"]},
    {"argv":["python3","-B","locales.py","--check","--source","data/en.json","--target","data/vi.json"],"kind":"REPRODUCTION","execution_context":"ACTUAL_CLI","expected_exit_code":1,"covers":["A1","P1"]}
  ]
}
```

Adapt the example to real project commands/data. A direct CLI check invokes the declared script directly (Python/Node script or project executable), without unittest/pytest/inline-code wrappers. Expected exits are fixed before execution; nonzero is supported only for ACTUAL_CLI, not timeout/missing executable. Add complete/noncheck/preservation checks as needed; `covers` remains an agent report, not semantic proof. Logs bind to declared source inputs. Do not use CODE to remove a previously approved workflow criterion or change the contract after checks.

## Resume and longer work, only when needed

`work context` reads this chat; without a provider identity use `work context --receipt NAME`. Never guess a recent task or ask the user to manage identifiers. Pause at a safe point with `work pause RECEIPT --summary "actual progress"`; another writer cannot be taken over. Reconcile real source changes before resuming.

Ordinary analysis/research stays in chat. If the user requests durable research context, save one short note with a unique filename for this chat in external artifact_directory (available in the setup result); retain its path in the chat. Do not call task/brief APIs, hunt payload schemas or create duplicate notes. The note reports facts/proposals and does not approve implementation.

Structured briefs are optional for approved work across several implementation milestones: [RECOVERY.md](RECOVERY.md). Load that schema only then. Use docs/help for a missing payload shape; do not inspect kit runtime implementation. More fields or records are not evidence of better decisions.

All operational payloads, receipts and logs stay in external artifact_directory. Product regression tests remain with product code. Passing tests does not publish or prove a UI is ready. State and cooperative writer records are same-user reports, not authenticated approval or OS filesystem enforcement.
