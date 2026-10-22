const fs=require('node:fs'),assert=require('node:assert/strict'),crypto=require('node:crypto');
(async()=>{
 global.crypto=crypto.webcrypto;
 const source=fs.readFileSync(require.resolve('../hosting/connection-worker.mjs'),'utf8');
 const load=async release=>(await import('data:text/javascript;base64,'+Buffer.from(source.replace("const ASSET_RELEASE='';","const ASSET_RELEASE='"+release+"';")).toString('base64'))).default;
 const worker=await load(''),objects=new Map();
 const digest=value=>crypto.createHash('sha256').update(value).digest('hex');
 const text=value=>typeof value==='string'?value:Buffer.from(value).toString();
 const env={PROCESSOR_REGISTRATION_SHA256:digest('test-only-key'),BUCKET:{
  get:async key=>objects.has(key)?{json:async()=>JSON.parse(text(objects.get(key))),text:async()=>text(objects.get(key)),body:objects.get(key)}:null,
  head:async key=>objects.has(key)?{}:null,put:async(key,value)=>objects.set(key,value)}};
 const call=(path,options={},handler=worker)=>handler.fetch(new Request('https://site.example'+path,options),env);
 const auth={Authorization:'Bearer test-only-key'};
 assert.equal((await call('/_processor/connection',{method:'PUT',body:'{}'})).status,401);
 assert.equal((await call('/_processor/connection',{method:'PUT',headers:auth,body:JSON.stringify({api_origin:'https://evil.example'})})).status,422);
 assert.equal((await call('/_processor/connection',{method:'PUT',headers:auth,body:JSON.stringify({api_origin:'https://example.trycloudflare.com'})})).status,200);
 const config=await call('/processor-config.json');assert.equal(config.headers.get('Cache-Control'),'no-store');
 assert.equal((await config.json()).api_origin,'https://example.trycloudflare.com');
 objects.set('assets/index.html','Legacy live site');
 const files={'index.html':'<head><script src="executive.js"></script></head><h1>Release one</h1>','executive.js':'console.log("one")','demo-data.json':'{}'};
 const manifest=JSON.stringify({files:Object.fromEntries(Object.entries(files).map(([key,value])=>[key,digest(value)]))}),release=digest(manifest);
 const seal=()=>call('/_processor/seal?release='+release,{method:'PUT',headers:auth,body:manifest});
 assert.equal((await seal()).status,422,'Incomplete release cannot be sealed');
 for(const [key,value] of Object.entries(files)){
  assert.equal((await call('/_processor/asset?release='+release+'&key='+key,{method:'PUT',headers:{...auth,'X-Asset-SHA256':digest(value)},body:value})).status,200);
 }
 assert.equal(await (await call('/')).text(),'Legacy live site','Staging does not change the live site');
 assert.equal((await seal()).status,200);
 const pinned=await load(release),html=await (await call('/',{},pinned)).text();
 assert(html.includes("window.REGDATA_ASSET_RELEASE='"+release+"'"));
 assert(html.includes('/_assets/'+release+'/executive.js'));
 assert.equal(await (await call('/_assets/'+release+'/executive.js',{},pinned)).text(),files['executive.js']);
 const nextFiles={...files,'executive.js':'console.log("two")'},nextManifest=JSON.stringify({files:Object.fromEntries(Object.entries(nextFiles).map(([key,value])=>[key,digest(value)]))}),nextRelease=digest(nextManifest);
 await call('/_processor/asset?release='+nextRelease+'&key=executive.js',{method:'PUT',headers:{...auth,'X-Asset-SHA256':digest(nextFiles['executive.js'])},body:nextFiles['executive.js']});
 assert.equal((await call('/_processor/seal?release='+nextRelease,{method:'PUT',headers:auth,body:nextManifest})).status,200);
 const newer=await load(nextRelease);
 assert.equal(await (await call('/executive.js',{},newer)).text(),nextFiles['executive.js']);
 assert.equal(await (await call('/executive.js',{},pinned)).text(),files['executive.js'],'Rollback restores prior assets, not just prior Worker code');
 assert.equal((await call('/_processor/asset?release='+release+'&key=executive.js',{method:'PUT',headers:{...auth,'X-Asset-SHA256':digest('wrong')},body:'tampered'})).status,422);
 assert.equal((await call('/_processor/asset?release='+release+'&key=../secret',{method:'PUT',headers:auth,body:'x'})).status,422);
 assert.equal((await call('/_processor/asset?release='+release+'&key=processor-config.json',{method:'PUT',headers:auth,body:'{}'})).status,422);
 console.log('Discovery and atomic publication: authentication, checksums, incomplete upload isolation, pinned HTML/assets and rollback passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
