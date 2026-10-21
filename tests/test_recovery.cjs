const assert=require('node:assert/strict');
const policy=require('../frontend/recovery.js');
assert.equal(policy.maxFailures,6);
assert.deepEqual([1,2,3,4,5,6].map(policy.delay),[2000,4000,8000,16000,30000,30000]);
for(const status of [400,401,403,404,410,422])assert.equal(policy.permanent({status}),true);
for(const status of [408,429,500,502,503,504])assert.equal(policy.permanent({status}),false);
assert.equal(policy.permanent(new TypeError('Failed to fetch')),false);
console.log('Recovery policy: permanent errors stop; transient errors back off within six failures.');
const fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require.resolve('../frontend/executive.js'),'utf8').split('(async()=>')[0];
function harness(status){
 const elements=new Map(),timers=new Map(),delays=[];let count=0;
 const element=s=>{if(!elements.has(s))elements.set(s,{textContent:'',hidden:false,disabled:false,classList:{toggle(){}}});return elements.get(s);};
 const context=vm.createContext({document:{querySelector:element,querySelectorAll:()=>[]},RegDataRecovery:policy,
  AbortSignal,URLSearchParams,URL,console,fetch:async()=>{count++;return{ok:status===200,status,json:async()=>status===200?{status:'ok',mode:'TEMPORARY_LOCAL_PILOT'}:{error:'Test error'}};},
  setTimeout:(fn,delay)=>{const id=delays.length+1;delays.push(delay);timers.set(id,fn);return id;},clearTimeout:id=>timers.delete(id)});
 vm.runInContext(source,context);vm.runInContext("origin='https://test.example';job={id:'test'};",context);
 return{context,elements,timers,delays,count:()=>count};
}
(async()=>{
 const missing=harness(404);await vm.runInContext('watch()',missing.context);
 assert.equal(missing.count(),1);assert.equal(missing.timers.size,0);
 assert.equal(vm.runInContext('pollPaused',missing.context),true);
 assert.match(missing.elements.get('#error').textContent,/404/);
 const offline=harness(503);for(let i=0;i<6;i++)await vm.runInContext('watch()',offline.context);
 assert.equal(offline.count(),6);assert.equal(offline.timers.size,0);
 assert.deepEqual(offline.delays,[2000,4000,8000,16000,30000]);
 assert.equal(offline.elements.get('#resume-status').hidden,false);
 const health=harness(200);vm.runInContext('jobActive=true;',health.context);await vm.runInContext('health()',health.context);
 assert.equal(health.elements.get('#build').disabled,true);
 const race=harness(200);let releasePreview;
 race.context.fetch=async url=>url.includes('/dataset')?await new Promise(resolve=>{releasePreview=()=>resolve({ok:true,json:async()=>({columns:['name'],rows:[]})});}):{ok:true,json:async()=>({id:'old',start:'20240331',end:'20240331',status:'COMPLETED_REVIEW_REQUIRED',result_ready:true,rows:1,columns:236})};
 const pending=vm.runInContext('watch()',race.context);
 for(let i=0;i<10&&!releasePreview;i++)await Promise.resolve();
 assert.equal(race.elements.get('#build').disabled,true,'Build stays disabled while preview is loading');
 await race.elements.get('#build-form').onsubmit({preventDefault(){}});
 assert.equal(vm.runInContext('job.id',race.context),'old','Overlapping submit is ignored');
 releasePreview();await pending;
 assert.equal(vm.runInContext('pollBusy',race.context),false);
 const capture=harness(200),names=[];capture.context.Blob=Blob;capture.context.URL=URL;
 capture.context.crypto=require('node:crypto').webcrypto;
 capture.context.document.createElement=()=>({click(){names.push(this.download);}});
 const bytes=new TextEncoder().encode('name\nOriginal\n');
 const hash=require('node:crypto').createHash('sha256').update(bytes).digest('hex');let releaseChunk;
 capture.context.fetch=async url=>url.includes('result-manifest')?{ok:true,json:async()=>({parts:1,chunk_size:1048576,bytes:bytes.length,sha256:hash})}:await new Promise(resolve=>{releaseChunk=()=>resolve({ok:true,arrayBuffer:async()=>bytes.buffer});});
 vm.runInContext("job={id:'old',start:'20240331',end:'20240331'};",capture.context);
 const downloading=vm.runInContext("download('result')",capture.context);
 for(let i=0;i<10&&!releaseChunk;i++)await Promise.resolve();
 assert.equal(capture.elements.get('#build').disabled,true);
 vm.runInContext("job={id:'new',start:'20250331',end:'20250331'};",capture.context);
 releaseChunk();await downloading;
 assert.equal(names[0],'regdata_20240331_20240331_236_columns.csv','Filename belongs to captured job');
 console.log('Repeated-build race and immutable download filename regressions passed.');
 console.log('Actual UI controller: 404 stops immediately; 503 pauses after six failures; health checks preserve an active build.');
})().catch(e=>{console.error(e);process.exitCode=1;});
