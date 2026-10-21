// Official scenario data are separate from bank financial observations.
document.querySelector('nav').insertAdjacentHTML('beforeend','<button id="fed-nav">Fed stress scenarios</button>');
document.querySelector('#fed-nav').onclick=async()=>{
 const id=++requestId;document.querySelectorAll('nav button').forEach(b=>b.classList.remove('active'));document.querySelector('#fed-nav').classList.add('active');
 content.innerHTML=heading('Fed stress scenarios','Loading official 2026 final scenario data…');
 try{
  const response=await fetch('fed-scenarios.json');if(!response.ok)throw Error('Scenario data unavailable');const data=await response.json();if(id!==requestId)return;
  const all=data.points.filter(p=>p.quarter>='2007 Q1');
  const dates=[...new Set(all.map(p=>p.quarter))].sort();
  const charts=[['unemployment','Unemployment rate','Percent'],['cre_yoy','Commercial real estate prices','Year-on-year change (%)'],['stock_yoy','Stock market price return','Year-on-year change (%)'],['bbb_spread','BBB corporate bond spread','Percentage points vs 10-year Treasury']];
  function chart(key,title,unit){
   const values=all.filter(p=>p[key]!==null).map(p=>p[key]);const low=Math.min(...values),high=Math.max(...values),pad=Math.max((high-low)*.08,.2),lo=low-pad,hi=high+pad;
   const x=q=>55+dates.indexOf(q)/(dates.length-1)*480,y=v=>235-(v-lo)/(hi-lo)*185;
   let marks='';for(let i=0;i<=4;i++){const value=lo+(hi-lo)*i/4;marks+=`<line x1="55" y1="${y(value)}" x2="535" y2="${y(value)}" stroke="#e2e8ee"/><text x="47" y="${y(value)+4}" text-anchor="end" font-size="11">${value.toFixed(1)}</text>`;}
   for(let i=0;i<dates.length;i+=12)marks+=`<text x="${x(dates[i])}" y="257" text-anchor="middle" font-size="11">${dates[i].slice(0,4)}</text>`;
   const boundary=x(all.find(p=>p.series==='severe').quarter);marks+=`<rect x="${boundary}" y="40" width="${535-boundary}" height="195" fill="#fff3e8" opacity=".6"/>`;
   for(const kind of ['actual','severe']){
    const rows=all.filter(p=>p.series===kind);if(kind==='severe')rows.unshift(all.filter(p=>p.series==='actual').at(-1));
    let d='',gap=true;for(const p of rows){if(p[key]===null){gap=true;continue;}d+=(gap?'M':'L')+x(p.quarter)+','+y(p[key])+' ';gap=false;}
    marks+=`<path d="${d}" fill="none" stroke="${kind==='actual'?'#172b46':'#c45b21'}" stroke-width="2.5" ${kind==='severe'?'stroke-dasharray="7 5"':''}/>`;
   }
   return `<article class="panel"><h2>${title}</h2><p class="muted">${unit}</p><svg viewBox="0 0 560 275" role="img" aria-label="${title}: historical observations and 2026 severely adverse scenario" style="width:100%;height:auto">${marks}</svg><p class="muted">${escapeHtml(data.definitions[key])}</p></article>`;
  }
  content.innerHTML=heading('2026 Fed stress scenarios','Four macroeconomic measures · final 2026 vintage · historical observations from 2007 shown')+
   '<p class="help-note"><strong>Solid navy:</strong> historical observations. <strong>Dashed orange / shaded area:</strong> hypothetical severely adverse scenario—not a forecast. These macro series do not extend the bank dataset’s historical coverage.</p>'+
   '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:18px">'+charts.map(args=>chart(...args)).join('')+'</div>'+
   '<div class="panel"><h2>Source and interpretation</h2><p>Charts recreated from the Federal Reserve’s final 2026 domestic CSVs. This is not an exact reproduction of the uploaded multi-year exhibit: 2020–2025 exercise paths are not included. Returns use four-quarter changes; the spread uses the 10-year Treasury benchmark. No bank losses or capital impacts are calculated.</p><p><a href="'+data.source_page+'" target="_blank" rel="noreferrer">Federal Reserve source page</a> · <a href="fed-scenarios.json" download>Download chart data, formulas and source hashes</a></p>'+data.sources.map(s=>'<p><a href="'+s.url+'" target="_blank" rel="noreferrer">'+escapeHtml(s.filename)+'</a> · '+s.rows+' quarters · Retrieved '+escapeHtml(s.retrieved_at_utc.slice(0,10))+'</p>').join('')+'</div>';
 }catch(error){content.innerHTML='<p class="error">'+escapeHtml(error.message)+'</p>';}
};
