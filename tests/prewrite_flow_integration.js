// Actual Python helper CLI + checked JavaScript flow, disposable test repo only.
const fs = require('node:fs');
const assert = require('node:assert/strict');
const {spawnSync} = require('node:child_process');
const {checkedPatchFlow} = require('../tools/checked_patch_flow.js');
const input = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const base = [input.cli, '--repo', input.repo, '--state-home', input.state];
let patchCalls = 0;
const invoke = (...args) => {
  const result = spawnSync(input.python, ['-B', ...base, ...args], {encoding:'utf8'});
  return {exit_code:result.status, output:result.stdout};
};
(async()=>{
  const result = await checkedPatchFlow({
    prepare: async()=>invoke('prepare-write',input.task,input.decision),
    recheck: async(ref)=>{
      fs.writeFileSync(input.reference,JSON.stringify(ref));
      if (input.mode === 'recheck-fails') {
        fs.writeFileSync(input.reference,JSON.stringify({...ref,sha256:'c'.repeat(64)}));
      }
      return invoke('check-write',input.task,input.reference);
    },
    patch: async(ref)=>{
      // Independently prove a real saved decision record exists before the file write.
      const read = spawnSync(input.python,['-B','-c',
        'import sqlite3,sys,json; c=sqlite3.connect("file:"+sys.argv[1]+"?mode=ro",uri=True); r=c.execute("SELECT id,content_json FROM workflow_documents WHERE id=?",(sys.argv[2],)).fetchone(); print(json.dumps({"id":r[0],"body":json.loads(r[1])}))',
        input.db,ref.record_id],{encoding:'utf8'});
      assert.equal(read.status,0,read.stderr);
      const record=JSON.parse(read.stdout);
      assert.equal(record.id,ref.record_id);assert.equal(record.body.milestone,'CONTRACT_DECISION');
      patchCalls++;fs.writeFileSync(input.target,'# patched after decision checkpoint\n');
      return {};
    }
  });
  console.log(JSON.stringify({result,patch_calls:patchCalls}));
})().catch(error=>{console.error(error);process.exitCode=1;});
