"""One resumable requested-range command; partial coverage is never silently complete."""
import argparse
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
import subprocess
import sys
from build_dataset import quarters


def utc():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


def completed_modern(root, period):
    mapping_hash=hashlib.sha256((root/'config/expanded_measures.json').read_bytes()).hexdigest()
    for path in sorted((root/'outputs/dataset').glob('*/release_report.json'), reverse=True):
        report = json.loads(path.read_text(encoding='utf-8'))
        if (report.get('requested_start') == report.get('requested_end') == period
            and report.get('processing_status') == 'COMPLETED' and not report.get('source_errors')
            and report.get('mapping_sha256')==mapping_hash
            and report.get('quality_policy')=='CAUTIOUS_FLOW_AND_COMPONENT_CHECKS_V1'
            and (path.parent/'organisation_financials.csv').is_file()
            and all(Path(s.get('snapshot','')).is_file() and
                    hashlib.sha256(Path(s['snapshot']).read_bytes()).hexdigest()==s.get('sha256')
                    for s in report.get('sources',[]))):
            return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args(argv)
    try:
        periods = quarters(args.start,args.end)
    except ValueError as error:
        parser.error(str(error))
    root=args.root.resolve()
    folder=root/'outputs/requests'/f'{args.start}-{args.end}'
    path=folder/'status.json'
    fields=json.loads((root/'config/expanded_measures.json').read_text(encoding='utf-8'))['fields']
    lower=max(f['valid_from'] for f in fields)
    upper=min(f['valid_to'] for f in fields)
    state={'start':args.start,'end':args.end,'started_at_utc':utc(),'status':'RUNNING',
           'current_mvp_complete':False,'periods':[],'result_files':[]}
    def update():
        state['updated_at_utc']=utc();save(path,state)
    def run(script, arguments, log):
        with log.open('w',encoding='utf-8') as handle:
            result=subprocess.run([sys.executable,str(root/'src'/script),'--root',str(root),*arguments],
                                  cwd=root,stdout=handle,stderr=subprocess.STDOUT,timeout=1800,check=False)
        return result.returncode
    update()
    try:
        for period in periods:
            item={'period':period,'status':'DOWNLOADING','output_ready':False}
            state['periods'].append(item);update()
            print(period,item['status'],flush=True)
            try:
                if lower<=period<=upper:
                    previous=completed_modern(root,period) if not args.refresh else None
                    before=set((root/'outputs/dataset').glob('*/release_report.json'))
                    item['status']='PROCESSING';update()
                    if previous:
                        report_path=previous;item['reused_completed_build']=True
                    else:
                        options=['--start',period,'--end',period]
                        if args.refresh: options.append('--refresh')
                        if args.offline: options.append('--offline')
                        code=run('build_dataset.py',options,folder/(period+'.log'))
                        new=set((root/'outputs/dataset').glob('*/release_report.json'))-before
                        if code not in (0,2) or len(new)!=1:
                            raise ValueError('Build failed; inspect local log')
                        report_path=new.pop()
                    report=json.loads(report_path.read_text(encoding='utf-8'))
                    if report.get('processing_status')!='COMPLETED' or report.get('source_errors') or report.get('quality_policy')!='CAUTIOUS_FLOW_AND_COMPONENT_CHECKS_V1':
                        raise ValueError('Source acquisition or processing blocked; inspect build report')
                    item.update(status='COMPLETED_REVIEW_REQUIRED',output_ready=True,
                                rows=report['organisation_quarters'],
                                failed_checks=report['failed_accounting_checks'],
                                unresolved_ownership=report['unresolved_ownership'],report=str(report_path))
                    state['result_files'].append(str(report_path.parent/'organisation_financials.csv'))
                else:
                    if not args.offline:
                        options=['--start',period,'--end',period,'--download']
                        if (root/'config'/('legacy_'+period+'.json')).is_file():
                            # Verified legacy financial pilot uses FDIC API bank data;
                            # don't also download the large SAS bank archive unnecessarily.
                            options+=['--family','holding_company']
                        if args.refresh: options.append('--refresh')
                        code=run('history_sources.py',options,folder/(period+'.log'))
                        item['acquisition_exit_code']=code
                    manifest=root/'research/history/chicago_manifest.json'
                    inventory=json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else {'archives':[]}
                    sources=[r for r in inventory['archives'] if r['period']==period]
                    item['sources']=[{k:r.get(k) for k in ('family','period','status','source_url','sha256')} for r in sources]
                    legacy_mapping=root/'config'/('legacy_'+period+'.json')
                    holder_ready=any(r['family']=='holding_company' and r.get('status')=='DOWNLOADED' for r in sources)
                    if legacy_mapping.is_file() and holder_ready:
                        item['status']='PROCESSING';update()
                        before=set((root/'outputs/legacy_financials').glob('*/release_report.json'))
                        options=['--period',period]
                        if args.offline: options.append('--offline')
                        if args.refresh: options.append('--refresh')
                        code=run('build_legacy_quarter.py',options,folder/(period+'-build.log'))
                        new=set((root/'outputs/legacy_financials').glob('*/release_report.json'))-before
                        if code not in (0,2) or len(new)!=1:
                            raise ValueError('Historical financial build failed; inspect local build log')
                        report_path=new.pop();report=json.loads(report_path.read_text(encoding='utf-8'))
                        if report.get('processing_status')!='COMPLETED' or report.get('source_errors'):
                            raise ValueError('Historical processing incomplete')
                        item.update(status='PARTIAL_REVIEW_REQUIRED',output_ready=True,
                                    rows=report['organisation_quarters'],failed_checks=report['failed_accounting_checks'],
                                    unresolved_ownership=report['unresolved_ownership'],quarantined_groups=report['quarantined_groups'],
                                    report=str(report_path),reason='Bounded verified measures only; excluded groups and unmapped fields require review')
                        state['result_files'].append(str(report_path.parent/'organisation_financials.csv'))
                    else:
                        item['status']='BLOCKED_HISTORICAL_MAPPING' if len(sources)==2 and all(r.get('status')=='DOWNLOADED' for r in sources) else 'BLOCKED_SOURCE_ACQUISITION'
                        item['reason']='No verified financial mapping for this period; archives alone are not a financial dataset.'
            except (ValueError,OSError,subprocess.TimeoutExpired) as error:
                item.update(status='BLOCKED',error=str(error))
            update();print(period,item['status'],flush=True)
        if state['result_files']:
            import csv
            target=folder/'organisation_financials.csv'
            columns=None
            with target.open('w',encoding='utf-8',newline='') as handle:
                for filename in state['result_files']:
                    with open(filename,encoding='utf-8-sig',newline='') as source:
                        reader=csv.DictReader(source)
                        if columns is None:
                            columns=reader.fieldnames;writer=csv.DictWriter(handle,fieldnames=columns);writer.writeheader()
                        if reader.fieldnames!=columns:
                            raise ValueError('Quarter column schemas differ; no merged result approved')
                        from serve_frontend import safe_csv
                        writer.writerows({k:safe_csv(v) for k,v in row.items()} for row in reader)
            state['combined_csv']=str(target)
        ready=sum(p['output_ready'] for p in state['periods'])
        partial=any(p['status']=='PARTIAL_REVIEW_REQUIRED' for p in state['periods'])
        state['status']='COMPLETED_REVIEW_REQUIRED' if ready==len(periods) and not partial else 'PARTIAL_REVIEW_REQUIRED' if ready else 'BLOCKED'
    except (ValueError,OSError) as error:
        state.update(status='FAILED',error=str(error))
    state['finished_at_utc']=utc();update()
    print(json.dumps({'status':state['status'],'report':str(path),'csv':state.get('combined_csv')},indent=2))
    return 0 if state['status']=='COMPLETED_REVIEW_REQUIRED' else 2


if __name__=='__main__':
    raise SystemExit(main())
