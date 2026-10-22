// Public assets are content-addressed. Each deployed Worker pins one sealed release.
const ASSET_RELEASE='';
const validKey=key=>/^(?:[a-z0-9-]+\.(?:html|js|css|json)|quarters\/\d{8}-[a-f0-9]{16}\.json)$/.test(key)&&key!=='processor-config.json';
const validHash=hash=>/^[a-f0-9]{64}$/.test(hash);
const json=(value,status=200)=>Response.json(value,{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
const hash=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(b=>b.toString(16).padStart(2,'0')).join('');
const validOrigin=value=>{try{const u=new URL(value);return u.protocol==='https:'&&/^[a-z0-9-]+\.trycloudflare\.com$/.test(u.hostname)&&u.origin===value&&!u.port;}catch{return false;}};
async function authorised(request,env){
 const value=request.headers.get('Authorization')||'';
 return !!env.PROCESSOR_REGISTRATION_SHA256&&value.startsWith('Bearer ')&&value.length<=200&&await hash(new TextEncoder().encode(value.slice(7)))===env.PROCESSOR_REGISTRATION_SHA256;
}
export default {async fetch(request,env){
 const url=new URL(request.url),path=url.pathname;
 if(path==='/processor-config.json'){
  if(request.method!=='GET')return json({error:'Method not allowed'},405);
  const stored=await env.BUCKET.get('_processor/connection.json');
  return json(stored?await stored.json():{api_origin:'',automatic_discovery:true});
 }
 if(path==='/_release.json'&&request.method==='GET')return json({release:ASSET_RELEASE||'legacy'});
 if(path.startsWith('/_processor/')){
  if(!await authorised(request,env))return json({error:'Unauthorised'},401);
  if(request.method!=='PUT')return json({error:'Method not allowed'},405);
  if(path==='/_processor/connection'){
   const text=await request.text();if(text.length>1024)return json({error:'Request too large'},413);
   let body;try{body=JSON.parse(text);}catch{return json({error:'Invalid JSON'},422);}
   if(!body||typeof body!=='object'||Object.keys(body).length!==1||!validOrigin(body.api_origin))return json({error:'Invalid processor origin'},422);
   await env.BUCKET.put('_processor/connection.json',JSON.stringify({api_origin:body.api_origin,automatic_discovery:true,updated_at_utc:new Date().toISOString()}),{httpMetadata:{contentType:'application/json'}});
   return json({registered:true});
  }
  const release=url.searchParams.get('release')||'';
  if(!validHash(release))return json({error:'Release required'},422);
  if(path==='/_processor/asset'){
   const key=url.searchParams.get('key')||'',digest=request.headers.get('X-Asset-SHA256')||'';
   if(!validKey(key)||!validHash(digest))return json({error:'Invalid asset'},422);
   if(Number(request.headers.get('Content-Length')||0)>24*1024*1024)return json({error:'Asset too large'},413);
   const bytes=await request.arrayBuffer();
   if(bytes.byteLength>24*1024*1024||await hash(bytes)!==digest)return json({error:'Asset checksum mismatch'},422);
   await env.BUCKET.put('blobs/'+digest,bytes);
   return json({uploaded:true});
  }
  if(path==='/_processor/seal'){
   const text=await request.text();
   if(text.length>65536||await hash(new TextEncoder().encode(text))!==release)return json({error:'Manifest checksum mismatch'},422);
   let manifest;try{manifest=JSON.parse(text);}catch{return json({error:'Invalid manifest'},422);}
   const entries=Object.entries(manifest?.files||{});
   if(!entries.length||entries.length>100||!manifest.files['index.html']||!manifest.files['executive.js']||!manifest.files['demo-data.json']||entries.some(([key,digest])=>!validKey(key)||!validHash(digest)))return json({error:'Invalid manifest'},422);
   const complete=await Promise.all(entries.map(([,digest])=>env.BUCKET.head('blobs/'+digest)));
   if(complete.some(value=>!value))return json({error:'Incomplete release; live site unchanged'},422);
   await env.BUCKET.put('releases/'+release+'.json',text);
   return json({sealed:true,release});
  }
  return json({error:'Not found'},404);
 }
 if(!['GET','HEAD'].includes(request.method))return json({error:'Method not allowed'},405);
 const pinned=/^\/_assets\/([a-f0-9]{64})\/(.+)$/.exec(path);
 const release=pinned?pinned[1]:ASSET_RELEASE,key=pinned?pinned[2]:(path==='/'?'index.html':path.slice(1));
 if(!validKey(key))return json({error:'Not found'},404);
 let manifest;
 if(release){
  const stored=await env.BUCKET.get('releases/'+release+'.json');
  if(!stored)return json({error:'Release unavailable'},503);
  manifest=await stored.json();
  if(!manifest.files[key])return json({error:'Not found'},404);
 }
 const asset=await env.BUCKET.get(release?'blobs/'+manifest.files[key]:'assets/'+key);
 if(!asset)return json({error:'Asset unavailable'},404);
 const type=key.endsWith('.html')?'text/html; charset=utf-8':key.endsWith('.js')?'text/javascript; charset=utf-8':key.endsWith('.css')?'text/css; charset=utf-8':'application/json';
 const headers=new Headers({'Cache-Control':pinned?'public, max-age=31536000, immutable':'no-cache','X-Content-Type-Options':'nosniff','Content-Type':type});
 let body=request.method==='HEAD'?null:asset.body;
 if(body&&release&&key.endsWith('.html')){
  body=(await asset.text()).replace('</head>',"<script>window.REGDATA_ASSET_RELEASE='"+release+"';</script></head>")
   .replace(/\b(src|href)="([^"]+)"/g,(match,attr,file)=>manifest.files[file]?attr+'="/_assets/'+release+'/'+file+'"':match);
 }
 return new Response(body,{headers});
}};
