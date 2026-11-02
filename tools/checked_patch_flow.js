// A4 repair: small provider-side sequence, not a writer or permission broker.
// Callbacks use existing tools. Source messages must be reviewed by the agent.
// Compatible with plain async JavaScript isolates; CommonJS export is tests only.
async function checkedPatchFlow(steps) {
  const trace = [];
  let patchCalled = false;
  const stopped = (stage, reason) => ({
    process_result: "STOPPED_NO_FURTHER_PATCH", stage, reason, trace,
    patch_called: patchCalled, trusted: false, write_authorized: false
  });
  const commandJSON = (result, expected) => {
    if (!result || result.exit_code !== 0 || result.session_id != null || result.isError === true) {
      throw new Error("Precondition tool did not complete successfully");
    }
    const body = JSON.parse(result.output);
    if (!body || body.process_result !== expected || body.trusted !== false ||
        body.write_authorized !== false || !body.checkpoint_ref) {
      throw new Error("Unexpected precondition response");
    }
    return body;
  };
  let stage = "prepare";
  try {
    const prepared = commandJSON(await steps.prepare(), "DECISION_CHECKPOINT_SAVED_UNVERIFIED");
    trace.push("decision_checkpoint_saved_and_read_back");
    stage = "recheck";
    const checked = commandJSON(await steps.recheck(prepared.checkpoint_ref), "DECISION_CHECKPOINT_RECHECKED_UNVERIFIED");
    // Bind exact reference keys/values; key order cannot change meaning.
    const a = prepared.checkpoint_ref, b = checked.checkpoint_ref;
    const keys = ["task_id", "record_id", "revision", "sha256", "contract_sha256", "contract_revision"];
    if (Object.keys(a).length !== keys.length || Object.keys(b).length !== keys.length ||
        keys.some(key => a[key] !== b[key] || a[key] == null) ||
        !["task_id", "record_id"].every(key => typeof a[key] === "string" && a[key].length > 0) ||
        !["sha256", "contract_sha256"].every(key => typeof a[key] === "string" && /^[0-9a-f]{64}$/.test(a[key])) ||
        !["revision", "contract_revision"].every(key => Number.isInteger(a[key]) && a[key] > 0)) {
      throw new Error("Checkpoint reference changed before patch");
    }
    trace.push("decision_checkpoint_rechecked");
    stage = "patch";
    patchCalled = true;
    const result = await steps.patch(checked.checkpoint_ref);
    if (result && result.isError === true) throw new Error("Patch tool reported an error");
    trace.push("provider_patch_called");
    return {process_result: "PATCH_TOOL_RETURNED_REVIEW_REQUIRED", trace,
      checkpoint_ref: checked.checkpoint_ref, patch_called: true,
      trusted: false, write_authorized: false};
  } catch (error) {
    return stopped(stage, String(error && error.message || error));
  }
}

if (typeof module !== "undefined" && module.exports) module.exports = {checkedPatchFlow};
