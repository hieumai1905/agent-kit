// Reproduce resolved exit_code=1, not only thrown exceptions. Fixture files only.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {checkedPatchFlow} = require('../tools/checked_patch_flow.js');
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'checked-flow-'));
const ref = {task_id:'T-fixture', record_id:'DOC-fixture', revision:1, sha256:'a'.repeat(64),
  contract_sha256:'b'.repeat(64), contract_revision:2};
const answer = (kind, reference=ref) => ({exit_code:0, output:JSON.stringify({
  process_result:kind, checkpoint_ref:reference, trusted:false, write_authorized:false})});
const prep = () => answer('DECISION_CHECKPOINT_SAVED_UNVERIFIED');
const check = () => answer('DECISION_CHECKPOINT_RECHECKED_UNVERIFIED');
(async () => {
  let cases = 0;
  const bad = [
    {exit_code:1,output:'AssertionError'}, {exit_code:2,output:'checkpoint save failed'},
    {}, {exit_code:0,output:'not JSON'}, {exit_code:0,output:'{}'},
    {...prep(),isError:true}, {...prep(),session_id:99}, {...prep(),exit_code:null},
    {exit_code:0,output:JSON.stringify({process_result:'BLOCKED'})},
    {exit_code:0,output:JSON.stringify({process_result:'DECISION_CHECKPOINT_SAVED_UNVERIFIED',checkpoint_ref:ref,trusted:true,write_authorized:true})}
  ];
  for (const result of bad) {
    const file = path.join(root, 'must-not-exist-'+cases);
    let rechecks = 0;
    const out = await checkedPatchFlow({prepare:async()=>result,
      recheck:async()=>{rechecks++;return check();}, patch:async()=>fs.writeFileSync(file,'bad')});
    assert.equal(out.patch_called,false);assert.equal(out.stage,'prepare');assert.equal(rechecks,0);
    assert.equal(fs.existsSync(file),false);cases++;
  }
  for (const result of [{exit_code:1,output:'source expired after checkpoint'}, {},
      answer('DECISION_CHECKPOINT_RECHECKED_UNVERIFIED',{...ref,revision:2}),
      answer('DECISION_CHECKPOINT_RECHECKED_UNVERIFIED',{...ref,extra:true})]) {
    const file=path.join(root,'blocked-after-save-'+cases);
    const out=await checkedPatchFlow({prepare:async()=>prep(),recheck:async()=>result,
      patch:async()=>fs.writeFileSync(file,'bad')});
    assert.equal(out.patch_called,false);assert.equal(out.stage,'recheck');assert.equal(fs.existsSync(file),false);cases++;
  }
  const thrown = await checkedPatchFlow({prepare:async()=>{throw Error('disk failure');},
    patch:async()=>{throw Error('must not be called');}});
  assert.equal(thrown.patch_called,false);cases++;
  const order=[];const marker=path.join(root,'decision-saved');const target=path.join(root,'valid-patch');
  const valid=await checkedPatchFlow({
    prepare:async()=>{fs.writeFileSync(marker,JSON.stringify(ref));order.push('saved');return prep();},
    recheck:async()=>{assert.equal(fs.existsSync(marker),true);order.push('rechecked');return check();},
    patch:async()=>{assert.equal(fs.existsSync(marker),true);assert.deepEqual(order,['saved','rechecked']);fs.writeFileSync(target,'after checkpoint');order.push('patched');return {};}
  });
  assert.equal(valid.process_result,'PATCH_TOOL_RETURNED_REVIEW_REQUIRED');assert.equal(valid.write_authorized,false);
  assert.deepEqual(order,['saved','rechecked','patched']);assert.equal(fs.readFileSync(target,'utf8'),'after checkpoint');cases++;
  const patchError=await checkedPatchFlow({prepare:async()=>prep(),recheck:async()=>check(),patch:async()=>({isError:true})});
  assert.equal(patchError.patch_called,true);assert.equal(patchError.stage,'patch');
  assert.equal(patchError.process_result,'STOPPED_NO_FURTHER_PATCH');cases++;
  console.log(JSON.stringify({pass:true,cases,negative_branch_sentinel_files_absent:true}));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>fs.rmSync(root,{recursive:true,force:true}));
