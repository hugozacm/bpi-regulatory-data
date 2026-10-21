// Public pilot: date ranges only. No credentials, filesystem paths or commands in requests.
window.RegDataProcessor={endpoint:'',selectedJob:'',current:null,online:false};
const processor=window.RegDataProcessor;
processor.ready=fetch('processor-config.json').then(r=>r.ok?r.json():{}).then(c=>{
 if(c.api_origin){const u=new URL(c.api_origin);if(u.protocol!=='https:'||u.username||u.password||u.pathname!=='/'||u.search||u.hash)throw Error('Invalid processor configuration');processor.endpoint=u.origin;}
}).catch(()=>{});
processor.request=async function(path,options={}){
 await processor.ready;if(!processor.endpoint)throw Error('Processor is not configured');
 if(!/^\/pilot\//.test(path))throw Error('Invalid processor route');
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),20000);
 try{const r=await fetch(processor.endpoint+path,{...options,credentials:'omit',signal:controller.signal});if(!r.ok){let d={};try{d=await r.json();}catch{}throw Error(d.error||'Processor request failed');}return r;}
 catch(error){if(error.name==='AbortError'||error instanceof TypeError)throw Error('Local processor is offline or unreachable. The owner must start the processor and tunnel. Published data remain available.');throw error;}
 finally{clearTimeout(timer);}
};
processor.download=async function(kind,query=''){
 const r=await processor.request('/pilot/jobs/'+processor.selectedJob+'/'+kind+(query?'?'+query:''));
 const u=URL.createObjectURL(await r.blob()),a=document.createElement('a');a.href=u;a.download=kind==='result'?'built_dataset_236_columns.csv':kind+(kind==='dictionary'||kind==='provenance'?'.json':'.csv');a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);
};
const publishedGet=get;
get=async function(url){
 if(processor.selectedJob&&url.startsWith('/api/dataset?'))return (await processor.request('/pilot/jobs/'+processor.selectedJob+'/dataset?'+url.split('?')[1])).json();
 return publishedGet(url);
};
processor.renderStatus=function(){
 const notice=document.querySelector('#processing-status');if(!notice)return;
 const record=processor.current;
 if(!record){notice.textContent=processor.online?'Processor online. Choose dates and press Build dataset.':'Checking the local processor…';return;}
 const stageNames={QUEUED:'Queued',CHECKING_SOURCES:'Checking saved files',DOWNLOADING:'Checking cache / downloading missing files',PROCESSING:'Building dataset',VALIDATING:'Validating',EXPORTING:'Writing results',COMPLETED_REVIEW_REQUIRED:'Completed — review required',BLOCKED:'Blocked',FAILED:'Failed',TIMED_OUT:'Timed out',INTERRUPTED:'Interrupted'};
 notice.innerHTML='<strong>'+escapeHtml(stageNames[record.status]||record.status)+'</strong><p>'+escapeHtml(record.message)+'</p><p>'+escapeHtml(readableQuarter(record.start))+' → '+escapeHtml(readableQuarter(record.end))+'</p>'+
  (record.result_ready?'<p>'+escapeHtml(record.rows)+' rows · 236 columns · '+escapeHtml(record.failed_accounting_checks)+' failed accounting checks · '+escapeHtml(record.unresolved_ownership)+' unresolved ownership records. These are unfiltered job results, not the published/quarantined snapshot.</p>':'')+
  '<p class="muted">'+(record.events||[]).map(e=>escapeHtml(stageNames[e.stage]||e.stage)).join(' → ')+'</p>';
 const button=document.querySelector('#build-dataset');if(button)button.disabled=!['COMPLETED_REVIEW_REQUIRED','BLOCKED','FAILED','TIMED_OUT','INTERRUPTED'].includes(record.status);
};
processor.controls=async function(){
 await processor.ready;if(document.querySelector('nav button.active')?.dataset.page!=='dataset'||document.querySelector('#processor-panel'))return;
 const panel=document.createElement('section');panel.id='processor-panel';panel.className='panel';
 panel.innerHTML='<h2>Build dataset for the selected range</h2><p>Select From and To in the explorer, then press Build dataset. Supported: <strong>2023 Q1–2026 Q2</strong>. One active job, one waiting slot; maximum 14 quarters and 10 jobs per day.</p><button id="build-dataset" class="primary">Build dataset</button> <button id="use-published">Return to published snapshot</button><div id="processing-status" role="status" aria-live="polite"></div><div id="job-downloads" class="toolbar"></div><p class="muted">Zero-cost local pilot. The owner’s computer and temporary HTTPS tunnel must stay running. The Quality page describes the published snapshot; use this job’s reports to check newly built data.</p><details><summary>Reconnect after the owner restarts the tunnel</summary><p>The temporary address changes after restart. Paste the new HTTPS address printed by the local launcher. This is an address, not a password.</p><input id="processor-address" type="url" aria-label="Processor HTTPS address"><button id="processor-reconnect">Check connection</button></details>';
 content.querySelector('h1').insertAdjacentElement('afterend',panel);
 const rangeNote=document.querySelector('#range-note');if(rangeNote)rangeNote.textContent='Apply filters searches loaded data. Build dataset processes the selected supported range. Earlier years are unavailable in this frontend pilot.';
 document.querySelector('.local').textContent=processor.selectedJob?'● Built job result · Local pilot':'● Published snapshot · Build pilot available';
 document.querySelector('#processor-address').value=processor.endpoint;
 document.querySelector('#processor-reconnect').onclick=async()=>{try{const u=new URL(document.querySelector('#processor-address').value);if(u.protocol!=='https:'||!u.hostname.endsWith('.trycloudflare.com')||u.username||u.password||u.search||u.hash||u.pathname!=='/')throw Error('Use the HTTPS trycloudflare.com origin printed by the local launcher');processor.endpoint=u.origin;const h=await(await processor.request('/pilot/health')).json();processor.online=h.status==='ok';processor.renderStatus();}catch(e){document.querySelector('#processing-status').textContent=e.message;}};
 document.querySelector('#use-published').onclick=()=>{processor.selectedJob='';search='';start='';end='';page=0;run(dataset);};
 document.querySelector('#build-dataset').onclick=async()=>{
  const button=document.querySelector('#build-dataset');button.disabled=true;
  try{
   const from=quarterEnd(document.querySelector('#from-year').value,document.querySelector('#from-q').value),to=quarterEnd(document.querySelector('#to-year').value,document.querySelector('#to-q').value);
   if(from>to||from<'20230331'||to>'20260630')throw Error('Choose an ordered range within 2023 Q1–2026 Q2.');
   processor.current=await (await processor.request('/pilot/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({start:from,end:to})})).json();processor.renderStatus();
   const poll=async()=>{
    try{
     processor.current=await (await processor.request('/pilot/jobs/'+processor.current.id)).json();processor.renderStatus();
     if(!['COMPLETED_REVIEW_REQUIRED','BLOCKED','FAILED','TIMED_OUT','INTERRUPTED'].includes(processor.current.status)){setTimeout(poll,2000);return;}
     if(processor.current.result_ready){processor.selectedJob=processor.current.id;start=processor.current.start;end=processor.current.end;search='';basis='';page=0;document.querySelector('[data-page="dataset"]').click();}
    }catch(error){const target=document.querySelector('#processing-status');if(target)target.textContent=error.message;if(document.querySelector('#build-dataset'))document.querySelector('#build-dataset').disabled=false;}
   };setTimeout(poll,1000);
  }catch(error){document.querySelector('#processing-status').textContent=error.message;button.disabled=false;}
 };
 processor.renderStatus();
 if(processor.selectedJob){
  const bar=document.querySelector('#job-downloads');
  for(const [kind,label] of [['result','Download built CSV (236 columns)'],['validation','Validation CSV'],['coverage','Coverage CSV'],['dictionary','Dictionary'],['provenance','Source provenance']]){
   const button=document.createElement('button');button.textContent=label;button.onclick=()=>processor.download(kind).catch(e=>{document.querySelector('#processing-status').textContent=e.message;});bar.append(button);
  }
 }
 if(!processor.current){try{const h=await (await processor.request('/pilot/health')).json();processor.online=h.status==='ok';processor.renderStatus();}catch(error){const target=document.querySelector('#processing-status');if(target)target.textContent=error.message;}}
};
