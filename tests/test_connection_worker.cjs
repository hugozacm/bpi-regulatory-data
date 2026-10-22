const fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 global.crypto=require('node:crypto').webcrypto;
 const source=fs.readFileSync(require.resolve('../hosting/connection-worker.mjs'),'utf8');
 const worker=(await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'))).default;
 const objects=new Map();
 const env={PROCESSOR_REGISTRATION_SHA256:require('node:crypto').createHash('sha256').update('test-only-key').digest('hex'),
  BUCKET:{get:async key=>objects.has(key)?{json:async()=>JSON.parse(objects.get(key)),body:objects.get(key),writeHttpMetadata:h=>h.set('Content-Type','text/html')}:null,
   put:async(key,value)=>objects.set(key,value)}};
 const call=(path,options={})=>worker.fetch(new Request('https://site.example'+path,options),env);
 assert.equal((await call('/_processor/connection',{method:'PUT',body:'{}'})).status,401);
 const auth={Authorization:'Bearer test-only-key'};
 assert.equal((await call('/_processor/connection',{method:'PUT',headers:auth,body:JSON.stringify({api_origin:'https://evil.example'})})).status,422);
 const realFetch=global.fetch;global.fetch=async()=>Response.json({status:'ok',mode:'TEMPORARY_LOCAL_PILOT'});
 assert.equal((await call('/_processor/connection',{method:'PUT',headers:auth,body:JSON.stringify({api_origin:'https://example.trycloudflare.com'})})).status,200);
 global.fetch=realFetch;
 const config=await call('/processor-config.json');assert.equal(config.headers.get('Cache-Control'),'no-store');
 assert.equal((await config.json()).api_origin,'https://example.trycloudflare.com');
 assert.equal((await call('/_processor/asset?key=quarters/20230331-48dd49d0c45b5b30.json',{method:'PUT',headers:auth,body:'[]'})).status,200);
 assert.equal((await call('/_processor/asset?key=../secret',{method:'PUT',headers:auth,body:'x'})).status,422);
 assert.equal((await call('/_processor/asset?key=processor-config.json',{method:'PUT',headers:auth,body:'{}'})).status,422);
 objects.set('assets/index.html','<h1>Existing site</h1>');assert.equal(await (await call('/')).text(),'<h1>Existing site</h1>');
 console.log('Discovery Worker: authentication, origin validation, no-cache registry and asset allowlist passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
