// Credentials remain only in this tab's memory, never in URLs or persistent storage.
window.RegDataBackend={base:'',key:'',job:null};
const backend=window.RegDataBackend;
function validBackend(value){
 const u=new URL(value);
 const local=location.hostname==='127.0.0.1'||location.hostname==='localhost';
 if(u.protocol!=='https:'&&!(local&&u.protocol==='http:'&&['127.0.0.1','localhost'].includes(u.hostname)))throw Error('Use an HTTPS backend address');
 if(u.username||u.password||u.search||u.hash||u.pathname!=='/')throw Error('Use only the backend origin, without credentials, paths or query parameters');
 return u.origin;
}
backend.ready=fetch('backend-config.json').then(r=>r.ok?r.json():{}).then(c=>{if(c.api_url)backend.base=validBackend(c.api_url);}).catch(()=>{});
backend.request=async function(path,options={}){
 if(!backend.base)throw Error('Hosted backend is not configured');
 if(!path.startsWith('/api/'))throw Error('Invalid API route');
 const headers={...(options.headers||{})};
 if(path.startsWith('/api/jobs'))headers.Authorization='Bearer '+backend.key;
 const r=await fetch(backend.base+path,{...options,headers,credentials:'omit'});
 if(!r.ok){let error;try{error=await r.json();}catch{}throw Error(error?.error||'Backend request failed');}
 return r;
};
backend.get=async path=>(await backend.request(path)).json();
backend.download=async function(path){const r=await backend.request(path);const u=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=u;a.download='regdata_research_draft.csv';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);};
backend.controls=function(){
 if(document.querySelector('#backend-panel'))return;
 const panel=document.createElement('details');panel.id='backend-panel';panel.className='panel';
 panel.innerHTML='<summary>Backend connection & operator processing</summary><p>The demo works without a backend. To use the Python API, enter its hosted HTTPS address. Starting a processing job requires an operator key; public visitors can browse only.</p><label>Backend address <input id="api-address" type="url" placeholder="https://your-backend.example"></label> <label>Operator key (optional for browsing) <input id="operator-key" type="password" autocomplete="off" placeholder="Kept in this tab only"></label><div class="toolbar"><button id="api-connect">Connect / check backend</button><button id="api-run">Process selected range</button><button id="api-disconnect">Disconnect</button></div><p id="api-notice" role="status"></p>';
 document.querySelector('#content').append(panel);
 document.querySelector('#api-address').value=backend.base;
 const notice=document.querySelector('#api-notice');
 notice.textContent=backend.base?'Backend address configured. Job results are separate review-required drafts, not automatically published.':'No hosted backend connected. Year filters do not start downloads.';
 document.querySelector('#api-connect').onclick=async()=>{
  try{const base=validBackend(document.querySelector('#api-address').value);const key=document.querySelector('#operator-key').value||backend.key;const r=await fetch(base+'/api/health',{credentials:'omit'});if(!r.ok)throw Error('Backend health check failed');const h=await r.json();if(h.status!=='ok')throw Error('Unexpected backend response');backend.base=base;backend.key=key;statusData=await backend.get('/api/status');run(dataset);}
  catch(e){notice.textContent=e.message;}
 };
 document.querySelector('#api-disconnect').onclick=()=>{backend.key='';backend.base='';location.reload();};
 document.querySelector('#api-run').onclick=async()=>{
  const button=document.querySelector('#api-run');
  try{
   if(!backend.base)throw Error('Connect a hosted backend first');
   backend.key=document.querySelector('#operator-key').value||backend.key;
   if(!backend.key)throw Error('An operator key is required to start processing');
   const from=quarterEnd(document.querySelector('#from-year').value,document.querySelector('#from-q').value);
   const to=quarterEnd(document.querySelector('#to-year').value,document.querySelector('#to-q').value);
   if(from>to)throw Error('From quarter must not be after To quarter');
   button.disabled=true;
   const job=await (await backend.request('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({start:from,end:to})})).json();
   backend.job=job.id;notice.textContent='Job accepted. Downloading cached/missing inputs and processing; this may take several minutes.';
   const poll=async()=>{try{const current=await backend.get('/api/jobs/'+job.id);const target=document.querySelector('#api-notice');if(target)target.textContent=current.status+': '+current.message;if(['QUEUED','RUNNING'].includes(current.status)){setTimeout(poll,5000);return;}button.disabled=false;if(current.result_ready&&target){const download=document.createElement('button');download.textContent='Download review-required job result';download.onclick=()=>backend.download('/api/jobs/'+job.id+'/result').catch(e=>{target.textContent=e.message;});target.append(document.createElement('br'),download);}}catch(e){if(document.querySelector('#api-notice'))document.querySelector('#api-notice').textContent=e.message;button.disabled=false;}};
   setTimeout(poll,1500);
  }catch(e){notice.textContent=e.message;button.disabled=false;}
 };
};
