"""Export an allowlisted public-data-only static demo; never copy source manifests or raw files."""
import hashlib
import argparse
import json
from pathlib import Path

import duckdb

from serve_frontend import ROOT, latest, snapshot, report

FIELDS = json.loads((ROOT/'config/public_columns.json').read_text(encoding='utf-8'))


def evidence_report(root, supplied=None):
    if supplied:
        path=Path(supplied)
        value=report(path)
        if value.get('processing_status') not in ('COMPLETED','PARTIAL'):
            raise ValueError('Evidence must be a completed or explicitly partial build')
        return value
    for path in sorted((root/'outputs/dataset').glob('*/release_report.json'),reverse=True):
        value=report(path)
        if value.get('processing_status') in ('COMPLETED','PARTIAL') and value.get('quality_policy')=='CAUTIOUS_FLOW_AND_COMPONENT_CHECKS_V1':
            return value
    raise ValueError('Build evidence required; run build_dataset.py or pass --evidence-report PATH')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-report',type=Path,help='Explicit build report; defaults to latest quality-gated build')
    args=parser.parse_args()
    out = ROOT / 'public_demo/dist'
    out.mkdir(parents=True, exist_ok=True)
    db = snapshot(ROOT)
    if not db:
        raise ValueError('Real interim dataset required')
    with duckdb.connect(str(db), read_only=True) as con:
        projection = ','.join(f'cast("{f}" as varchar)' for f in FIELDS)
        rows = con.execute('SELECT '+projection+' FROM organisation_financials ORDER BY report_date,entity_key').fetchall()
    m = report(db.parent / 'mvp_manifest.json')
    allowed = ['rows','columns','periods','financial_tests_passed','financial_tests_failed','financial_tests_not_testable',
               'financial_tests_failed_input','financial_rows_quarantined','additional_bank_only_groups_excluded',
               'unresolved_ownership_records','uncertain_quarter_values_withheld']
    h = report(latest(ROOT, 'outputs/history/*/history_report.json')) or {}
    history_keys = ['status','reported_values','periods_loaded','missing_requested_periods','requested_coverage_complete','limitations']
    status = {'interim': {k:m[k] for k in allowed}, 'history': {k:h[k] for k in history_keys if k in h},
              'scope': {'current_delivery_status':'INCOMPLETE_HISTORICAL_MVP'},
              'mode':'Published snapshot plus optional connected local processor', 'demo_columns':len(FIELDS)}
    # Quarter shards keep each static asset bounded without withholding columns.
    from collections import defaultdict
    shards=defaultdict(list)
    date_column=FIELDS.index('report_date')
    for row in rows:
        shards[row[date_column]].append(row)
    directory=out/'quarters'
    directory.mkdir(exist_ok=True)
    shard_files={}
    total_bytes=0
    for period, records in shards.items():
        payload=json.dumps(records,separators=(',',':')).encode()
        if len(payload)>24*1024*1024:
            raise ValueError('Quarter exceeds static asset size limit; further partitioning needed')
        digest=hashlib.sha256(payload).hexdigest()[:16]
        filename=f'quarters/{period}-{digest}.json'
        (out/filename).write_bytes(payload)
        shard_files[period]=filename
        total_bytes+=len(payload)
    data = {'columns':FIELDS,'dates':sorted(shards),'bases':sorted({r[FIELDS.index('basis')] for r in rows}),
            'shards':shard_files,'snapshot':db.parent.name,'status':status}
    encoded = json.dumps(data,separators=(',',':')).encode()
    (out / 'demo-data.json').write_bytes(encoded)
    (out / 'demo-status.json').write_text(json.dumps(status,separators=(',',':')),encoding='utf-8')
    # Public evidence is explicitly allowlisted: never publish workstation paths or full receipts.
    pilot = evidence_report(ROOT,args.evidence_report)
    evidence_keys = ['requested_start', 'requested_end', 'processing_status', 'finished_at_utc',
                     'organisation_quarters', 'duplicate_keys', 'unresolved_ownership',
                     'failed_accounting_checks', 'historical_scope_complete', 'approved_final_dataset',
                     'mapping_sha256', 'release_blockers']
    evidence = {k: pilot[k] for k in evidence_keys}
    evidence['sources'] = [{k: s.get(k) for k in ('filename', 'period', 'sha256', 'acquisition')}
                           for s in pilot['sources']]
    evidence['test_boundary'] = 'Saved-source build evidence; not proof of fresh cloud acquisition or financial certification.'
    (out / 'pilot-evidence.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    guide = {'mode': 'Published snapshot browsing plus an optional connected local-processing pilot for 2023 Q1–2026 Q2.',
             'financial_units': 'USD thousands', 'missing_values': 'Unavailable or withheld; never zero',
             'available_periods': m['periods'], 'public_columns': FIELDS,
             'full_local_columns': m['columns'],
             'workflow': ['Select From/To quarters in Workspace',
                          'Prepare dataset submits a bounded job to the running local processor',
                          'The worker checks cached files, acquires missing inputs, builds and validates',
                          'Withhold uncertain quarterly flows, retain input checks, quarantine accounting conflicts and validate delivered rows',
                          'Completed job results load without republishing; download all 236 columns and supporting reports',
                          'Published snapshot remains available when the processor is offline'],
             'limitations': ['Historical financial integration incomplete',
                             'All 236 columns are included; unavailable or withheld cells remain blank',
                             'Predecessors remain separate before official mergers; no always-merged history',
                             'Consolidated holding-company and bank-only figures have different scopes',
                             'Accounting checks do not establish full financial accuracy']}
    (out / 'dataset-guide.json').write_text(json.dumps(guide, indent=2), encoding='utf-8')
    for name in ('index.html','style.css','backend.js','backend-config.json','processor.js','processor-config.json'):
        text = (ROOT/'frontend'/name).read_text(encoding='utf-8')
        if name == 'index.html':
            text = text.replace('Local · Read-only','Public demo · Static snapshot').replace('Local research prototype','Public research demo')
        (out/name).write_text(text,encoding='utf-8')
    index=out/'index.html'
    index.write_text(index.read_text(encoding='utf-8').replace('</body>','<script src="processor.js"></script></body>'),encoding='utf-8')
    app = (ROOT/'frontend/app.js').read_text(encoding='utf-8')
    old = "async function get(url){if(window.RegDataBackend){await RegDataBackend.ready;if(RegDataBackend.base)return RegDataBackend.get(url);}const r=await fetch(url);const d=await r.json();if(!r.ok)throw Error(d.error||'Request failed');return d;}"
    adapter = '''let demoPromise;
async function get(url){
 if(url==='/api/status'){const r=await fetch('demo-status.json');if(!r.ok)throw Error('Demo summary unavailable');return r.json();}
 if(!demoPromise)demoPromise=fetch('demo-data.json').then(r=>{if(!r.ok)throw Error('Demo data unavailable');return r.json();});
 const data=await demoPromise;
 if(url==='/api/status')return data.status;
 const p=new URL(url,location.origin).searchParams;
 const dates=data.dates;
 const wanted=dates.filter(q=>(!p.get('start')||q>=p.get('start'))&&(!p.get('end')||q<=p.get('end'))&&(!p.get('report_date')||q===p.get('report_date')));
 data.cache??={};
 const chunks=await Promise.all(wanted.map(q=>data.cache[q]??(data.cache[q]=fetch(data.shards[q]).then(async r=>{if(!r.ok)throw Error('Quarter data unavailable: '+q);return r.json();}).catch(error=>{delete data.cache[q];throw error;}))));
 const objects=chunks.flat();
 const s=(p.get('search')||'').toLowerCase();
 if(p.get('start')&&p.get('end')&&p.get('start')>p.get('end'))throw Error('From quarter must not be after To quarter');
 const indexes=['name','entity_key','top_rssd'].map(c=>data.columns.indexOf(c)), basisIndex=data.columns.indexOf('basis');
 const filtered=objects.filter(r=>(!s||indexes.some(i=>(r[i]||'').toLowerCase().includes(s)))&&(!p.get('basis')||r[basisIndex]===p.get('basis')));
 const page=Number(p.get('page')||0);
 return {rows:filtered.slice(page*50,page*50+50).map(r=>Object.fromEntries(data.columns.map((c,i)=>[c,r[i]]))),total:filtered.length,columns:data.columns,dates,bases:data.bases,page,snapshot:data.snapshot,exportRows:filtered};
}
function csvValue(v){let s=String(v??'');if(/^[\\s]*[=+@-]/.test(s)&&!/^[-]?\\d+$/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';}
document.addEventListener('click',async e=>{if(e.target.id!=='export')return;e.preventDefault();try{if(window.RegDataProcessor?.selectedJob){await RegDataProcessor.download('result',params().toString());return;}if(window.RegDataBackend?.base){await RegDataBackend.download('/api/export?'+params());return;}const d=await get('/api/dataset?'+params());const parts=['\\ufeff'+d.columns.map(csvValue).join(',')+'\\r\\n'];for(const row of d.exportRows)parts.push(row.map(csvValue).join(',')+'\\r\\n');const u=URL.createObjectURL(new Blob(parts,{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=u;a.download='public_demo_filtered.csv';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}catch(err){alert(err.message);}});
'''
    if old not in app:
        raise ValueError('Frontend adapter interface changed; review required')
    app = app.replace(old, adapter)
    # This public stage has no hosted execution service; do not ask visitors for credentials.
    app = app.replace('window.RegDataBackend?.controls();', '')
    app += '''
const publishedOverview=overview;
overview=function(){publishedOverview();content.insertAdjacentHTML('beforeend',
 '<div class="panel"><h2>How this website works</h2><p><strong>1. Choose dates.</strong> Open Dataset explorer and select From/To quarters.</p><p><strong>2. Build dataset.</strong> For 2023 Q1–2026 Q2, submit a job to the running local processor. It checks cached sources, downloads missing inputs, builds and validates. Watch the actual status.</p><p><strong>3. Explore and download.</strong> A completed job loads into the explorer without republishing the site. Download its CSV, validation, coverage, dictionary and source provenance. Apply filters only filters data; Build dataset starts processing.</p><p>The computer and temporary tunnel must stay running. If offline, the published snapshot is still available. All 236 columns are selectable and included in CSV exports.</p><a href="dataset-guide.json" download>Download dataset guide</a></div><div class="panel"><h2>What preparation was applied?</h2><p>Y-9C and FDIC Call Report-derived data were aligned by quarter and institution identifiers. Dated ownership was used for grouping; subsidiary core balances were not added again to consolidated holding-company balances. Deposit detail stays separate. Stocks remain quarter-end balances; compatible YTD flows are differenced, with uncertain values withheld. Known conflicting rows were quarantined in the published snapshot; newly built job results are unfiltered research drafts with their own validation.</p><p>Predecessors remain separate before official merger dates: no always-merged historical series is claimed. Field mappings are bounded to verified periods; complete historical field-label harmonisation is not finished. Missing is not zero, and these checks do not certify financial accuracy.</p></div>'+
 '<div class="panel"><h2>Latest local pipeline trial: 2024 Q1</h2><p>4,335 organisation-quarter rows · 0 duplicate keys · 0 failed accounting checks · 29 unresolved ownership records.</p><p>This is separate test evidence, not a replacement for the 14-quarter published snapshot. It used cached official sources; it does not prove unattended cloud downloads or financial certification.</p><a href="pilot-evidence.json" download>Download pilot validation summary</a></div>');};
'''
    replacements = {'A local workspace':'A public demo', 'actual local snapshot':'public snapshot',
        'actual local outputs':'public source outputs', 'Actual local outputs':'Real public-source outputs',
        'The dataset explorer queries the existing local DuckDB output.':'The dataset explorer includes all 236 columns from the real interim output; choose displayed columns or export the complete filtered CSV.',
        'latest local staging report':'recorded staging report', 'Latest raw staging run':'Recorded raw staging run',
        'Latest local staging report':'Recorded staging report', 'Export filtered CSV (all columns)':'Export filtered CSV (236 columns)',
        'Main columns':'Full local dataset columns', 'local package\'s':'original package\'s'}
    for before,after in replacements.items():
        app=app.replace(before,after)
    app=app.replace('Integrate verified historical financial mappings and dated ownership into one main organisation-quarter dataset. Archive discovery and raw staging do not satisfy this gate.',
                    'For this frontend pilot, use the available 2023 Q1–2026 Q2 range. Open Dataset explorer, choose dates and press Build dataset. Historical expansion is paused; it is not silently claimed complete.')
    (out/'app.js').write_text(app,encoding='utf-8')
    fed = ROOT / 'research/fed_scenarios/fed-scenarios.json'
    if fed.is_file():
        (out/'fed-scenarios.json').write_bytes(fed.read_bytes())
        (out/'fed.js').write_text((ROOT/'frontend/fed.js').read_text(encoding='utf-8'),encoding='utf-8')
        index = out/'index.html'
        index.write_text(index.read_text(encoding='utf-8').replace('</body>','<script src="fed.js"></script></body>'),encoding='utf-8')
    # The public executive interface deliberately has no institution/column filters.
    # Retain legacy assets for local compatibility, but do not load those scripts.
    for source, target in [('executive.html', 'index.html'), ('executive.css', 'executive.css'), ('executive.js', 'executive.js'), ('bpi-brand.css', 'bpi-brand.css'), ('recovery.js', 'recovery.js')]:
        (out/target).write_bytes((ROOT/'frontend'/source).read_bytes())
    audit={'rows':len(rows),'demo_columns':FIELDS,'source_database_sha256':hashlib.sha256(db.read_bytes()).hexdigest(),
           'public_json_sha256':hashlib.sha256(encoded).hexdigest(), 'bytes':len(encoded)+total_bytes,
           'quarter_files':shard_files,
           'limitations':['Live execution requires the connected local processor', 'Pilot coverage is 2023 Q1–2026 Q2; earlier history is not included']}
    (ROOT/'public_demo/EXPORT_AUDIT.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    print(json.dumps({'rows':len(rows),'columns':len(FIELDS),'bytes':len(encoded)+total_bytes}))


if __name__=='__main__':
    main()
