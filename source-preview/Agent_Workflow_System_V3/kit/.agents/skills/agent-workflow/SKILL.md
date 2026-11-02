---
name: agent-workflow
description: Use this skill to normalize an incoming coding request, prepare a task contract, validate it, request human approval, execute an approved task, or hand off to a new agent/session.
---

Read `AGENTS.md`, `docs/agentflow/WORKFLOW.md`, and the active task's request/contract/state. Prior to approval: read-only exploration plus editing only the active `contract.json`. Use `python3 .agentflow/bin/agentflow.py propose <TASK_ID>` to validate and render the SPEC, show it in full to the user, and wait for their exact approval message `Duyệt`. Do not start code edits. After approval, confirm status, honor scope and locks, implement small verified steps, write an accurate checkpoint to `STATE.md`. If you discover a material scope change, return to preflight. Model routing only recommends; do not auto-switch platforms or rely on subagents. Never impersonate the user's approval.
