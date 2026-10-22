// Stable discovery and public assets; never proxy arbitrary URLs or processing jobs.
const json=(value,status=200)=>Response.json(value,{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
const validOrigin=value=>{try{const u=new URL(value);return u.protocol==='https:'&&/^[a-z0-9-]+\.trycloudflare\.com$/.test(u.hostname)&&u.origin===value&&!u.port;}catch{return false;}};
async function authorised(request,env){
 const value=request.headers.get('Authorization')||'';
 if(!env.PROCESSOR_REGISTRATION_SHA256||!value.startsWith('Bearer ')||value.length>200)return false;
 const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value.slice(7)));
 return [...new Uint8Array(digest)].map(b=>b.toString(16).padStart(2,'0')).join('')===env.PROCESSOR_REGISTRATION_SHA256;
}
export default {async fetch(request,env){
 const url=new URL(request.url),path=url.pathname;
 if(path==='/processor-config.json'){
  if(request.method!=='GET')return json({error:'Method not allowed'},405);
  const stored=await env.BUCKET.get('_processor/connection.json');
  return json(stored?await stored.json():{api_origin:'',automatic_discovery:true});
 }
 if(path.startsWith('/_processor/')){
  if(!await authorised(request,env))return json({error:'Unauthorised'},401);
  if(request.method!=='PUT')return json({error:'Method not allowed'},405);
  if(path==='/_processor/connection'){
   if(Number(request.headers.get('Content-Length')||0)>1024)return json({error:'Request too large'},413);
   const text=await request.text();if(text.length>1024)return json({error:'Request too large'},413);
   let body;try{body=JSON.parse(text);}catch{return json({error:'Invalid JSON'},422);}
   if(Object.keys(body).length!==1||!validOrigin(body.api_origin))return json({error:'Invalid processor origin'},422);
   // The owner launcher verifies pilot health before registering. Do not proxy
   // or fetch submitted URLs here; the browser independently checks live health.
   const value={api_origin:body.api_origin,automatic_discovery:true,updated_at_utc:new Date().toISOString()};
   await env.BUCKET.put('_processor/connection.json',JSON.stringify(value),{httpMetadata:{contentType:'application/json'}});
   return json({registered:true});
  }
  if(path==='/_processor/asset'){
   const key=url.searchParams.get('key')||'';
   if(!/^(?:[a-z0-9-]+\.(?:html|js|css|json)|quarters\/\d{8}-[a-f0-9]{16}\.json)$/.test(key)||key==='processor-config.json')return json({error:'Invalid asset'},422);
   if(Number(request.headers.get('Content-Length')||0)>24*1024*1024)return json({error:'Asset too large'},413);
   await env.BUCKET.put('assets/'+key,request.body,{httpMetadata:{contentType:request.headers.get('Content-Type')||'application/octet-stream'}});
   return json({uploaded:true});
  }
  return json({error:'Not found'},404);
 }
 if(!['GET','HEAD'].includes(request.method))return json({error:'Method not allowed'},405);
 const key=path==='/'?'index.html':path.slice(1);
 if(!/^(?:[a-z0-9-]+\.(?:html|js|css|json)|quarters\/\d{8}-[a-f0-9]{16}\.json)$/.test(key))return json({error:'Not found'},404);
 const asset=await env.BUCKET.get('assets/'+key);
 if(!asset)return json({error:'Asset unavailable'},404);
 const headers=new Headers({'Cache-Control':'no-cache','X-Content-Type-Options':'nosniff'});asset.writeHttpMetadata(headers);
 return new Response(request.method==='HEAD'?null:asset.body,{headers});
}};
