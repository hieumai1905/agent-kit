# Recovery and advanced APIs — v1.1.1

Version 1.1.1 retains repair/context/cooperative writer APIs. Ordinary work starts at QUICKSTART.md; this document is for recovery and longer work. Use the default INIT_PROMPT.md for explicit setup/upgrade; existing chats never upgrade automatically.

## Pending changes and the actual decision

`propose-contract "specific existing task" /EXTERNAL/proposal.json` now saves a separate CONTRACT_PROPOSAL draft and returns proposal_revision. It does not replace the active contract, decision, progress or receipt. A later draft requires `--expected-revision N` using the observed proposal revision; stale writes fail. Legacy history is retained. Merely storing a draft never approves it.

Explain the extra decision in chat using [DECISIONS.md](DECISIONS.md). Continue only independent previously authorized work after recheck; pause dependent work. When uncertain about independence, pause at a safe point. New effect types/roots/boundaries require an actual USER decision, never an approval inferred from state.

When the USER refers to a saved proposal, read `work proposal "specific task"` first and preserve its exact paths/checks. Begin/start detect path overlap with pending work and return a read-only reconciliation command instead of creating a duplicate scope under another title. Follow that command, compare the actual USER decision with the saved proposal and accept only the approved version. A path overlap is a hint to reconcile, not proof of meaning or approval; disjoint independent work remains possible. Do not switch APIs to bypass the overlap.

For an actual USER rejection/cancellation, use `work reject-proposal TOPIC --proposal-revision N --source-ref "Actual USER rejection"`. It records rejection of that exact pending version and leaves active scope/decision/receipt intact. Rejected/consumed drafts cannot be accepted by replay. Do not reject a draft yourself merely to unblock a new overlapping task.

After that decision, the advanced path uses:

```sh
HELPER work accept-proposal "specific existing task" --proposal-revision N --source-ref "Actual USER decision approving this exact presented proposal"
```

Use the observed proposal_revision, not the contract revision. The pending contract must contain explicit repositories/files, work_type, preservation and checks. Active receipt writers must pause/handoff before a scope change. The command atomically verifies the base/pending version, consumes the draft and changes the active contract, then saves/readbacks/rechecks the actual reported decision before returning. Do not start/checkpoint that decision again. After patching, run its next_command immediately before tests to capture sources; fill the returned finish_input_example with actual checks/results and send it to work finish TOPIC --data -. Failure after activation leaves no matching old decision: stop and reconcile, never retry activation blindly. Old evidence/receipts stay historical. A receipt milestone may instead pause/handoff and begin a distinct newly authorized milestone. There is no OS write grant or trusted USER authentication.

Context reports writer ownership as THIS_CHAT, OTHER_CHAT, IDLE or UNKNOWN (receipt-only fallback is labelled explicitly). A matching active receipt is continuation of this chat, not another owner's lock. OWN_ACTIVE_WORK means read work context and use that receipt; never call begin repeatedly or ask the user to release another chat. Unknown/mismatched ownership requires reconciliation, not takeover.

The low-level core CLI retains its draft revision primitive for compatibility. Normal operations use the runtime command above; do not use a low-level API to replace scope while a review is pending or bypass a conflict.

## Normal task and repair

Use the complete helper prefix shown in AGENTS.md. `HELPER` below is shorthand, not a file or executable to create.

```sh
HELPER work begin "Observable task" --data -
HELPER work verify /RETURNED/begin-receipt.json
# If TESTS_FAILED: inspect returned log_files, then prepare before editing again.
HELPER work retry /RETURNED/verification-receipt.json --summary "Observed failure and intended same-scope repair"
HELPER work verify /RETURNED/retry-receipt.json
HELPER work handoff /RETURNED/verification-receipt.json --summary "Actual outcome" --remaining "Actual UI still untested"
```

`retry` persists, reads back and rechecks a batch under the same approved contract. It cannot change scope, repositories, test commands or requirements. No new human approval is requested for an already approved repair. A changed behavior/excluded path still needs contract review. Failed tests remain failed in historical records; old receipts, changed logs, concurrent source changes and changed contracts never become PASS. Missing commands/timeouts are failures. Short receipt names resolve only in this repository artifact directory; `next_command` is an argv suffix for the known helper prefix. Repeating verify with its latest verification receipt reuses evidence only if the declared source manifest, logs, scope and binding remain current. Any declared source change invalidates reuse; all declared checks run after retry, conservatively avoiding unsafe semantic guesses about which check depends on which file.

TESTS_FAILED has repair instructions. Other BLOCKED/errors require reconciliation before product edits. Never ignore a nonzero exit or switch to the advanced API to bypass a block. A short display is separate from the complete Git observation: 120 dirty entries alone is not an error. The bounded Git command may still fail on timeout, malformed output or more than 1 MiB; those are explicit unavailable observations and remain blocking. The independent artifact inventory also retains its own bounds.

## Shared project outcome across milestones

For a small task, the ordinary short contract suffices. When several milestones need durable requirements, the first approved begin payload can also contain:

```json
{
  "brief": {
    "outcome": "Three editable ways to produce a new video in Space",
    "requirements": [
      {"key":"manual","text":"Manual editing produces video","source":"USER message approving three usage paths"},
      {"key":"assistant","text":"Space assistant is the chat assistant, distinct from the Agent node","source":"USER clarification"},
      {"key":"template","text":"A community template runs with a new topic/language without chat","source":"USER template requirement"}
    ],
    "must_preserve": ["Existing node purposes and outputs"],
    "examples": [{"input":"Analyze and propose this video","actions":"Discuss the plan before execution","expected":"Revisable proposal; no nodes run automatically"}],
    "open_questions": ["Actual browser interaction remains untested"]
  },
  "addresses": ["manual"]
}
```

Merge these fields into the normal begin object containing contract, approval_source and checks. Examples describe the product's actual users and operations; do not paste the video example into unrelated projects. Later begins reuse the saved brief and declare their own addresses. Handoff shows requirements deferred by that milestone, not a global completion claim. A reported mapping cannot prove semantic coverage or real usability. Review the original USER sources and actual result. Open questions are not confirmed requirements.

`work brief` reads the current brief. For a reviewed revision, first handoff/pause active work, then use `work brief --data - --expected-revision N` from the read result. Conflicting/stale versions stop; changes do not transfer an old approval. Existing receipts bind the version they used. Preserve history and reconcile old work rather than resetting tasks.

## Chat context and one cooperative writer

```sh
HELPER work context
HELPER work pause /RETURNED/latest-receipt.json --summary "Actual progress and safe pause reason"
# Later, in the same chat, inspect context and current sources before resuming.
HELPER work retry /RETURNED/pause-receipt.json --summary "Same approved scope remains current"
```

The provider's AGENTFLOW_SESSION, CODEX_THREAD_ID or CLAUDE_SESSION_ID identifies the chat automatically, in that priority order. Do not supply an override in ordinary work. A redundant legacy alias is ignored when provider identity exists; it never selects another chat. When unavailable, begin returns an anonymous session_ref; the agent retains it and uses `work context --session REF` or `--receipt PATH`. The hidden legacy `work begin --session REF` remains only as an advanced fallback when no provider identity exists; receipts are preferred. Never guess another chat's current task or ask the user to manage IDs. Context is read-only and grants no permission. It cannot erase or compact the app's chat history; detailed logs stay external, and the agent should load them only to answer a specific question. A fresh chat needs explicit handoff and current USER scope, not hidden approval carried from state.

The normal begin path and setup/upgrade acquire a repository writer using a SQLite compare-and-set record. The record is independent of chat pointers: two chats retain separate histories, while one cooperating operation prepares writes. Busy returns the owner and task; it never expires into permission or automatically takes over. Save handoff or pause at a safe point. Pause records unexpected changes without reverting them, and releases the turn without declaring completion. Resuming paused work rejects changed declared sources; inspect and reconcile concurrent work rather than absorbing it as your patch.

If a preparation process exited before returning any receipt, its own chat can run `work pause --summary "Observed interruption"`. It refuses active work, a live PID or another owner; it saves the observation and releases only that interrupted preparation. A reused PID is treated conservatively as live. No forced takeover/reset is provided.

This is cooperative coordination, not filesystem enforcement or authenticated ownership. Older kit versions, advanced APIs and arbitrary provider tools do not automatically acquire this record; all writers must follow the same protocol before relying on it. Never upgrade or contact another live chat without USER authorization. Tests of simultaneous callers are local processes using disposable state, not changes to live chats.

## Local-only artifacts and acceptance

Briefs, writer records, chat pointers, receipts and logs stay in external state covered by artifact inventory/INDEX checks. Product regression tests remain with product code. Do not add kit operations to a project commit, force-add guidance, change hooks, or unstage/untrack user files.

Command checks establish only their measured behavior. UI acceptance, application readiness and pending requirements remain explicit. Efficiency requires matched completed tasks; report elapsed time, human corrections, helper calls, input/cached/uncached/output separately. Cached input is a subset of input. Do not convert incomplete or timed-out controls into a savings percentage.
