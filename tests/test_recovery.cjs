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
 console.log('Actual UI controller: 404 stops immediately; 503 pauses after six failures; health checks preserve an active build.');
})().catch(e=>{console.error(e);process.exitCode=1;});
