"""Bounded March-2001 financial pilot with 236-column delivery schema and explicit gaps."""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from bpi_pipeline import as_int, load_fdic_json, sha256, validate_records, write_csv
from history_audit import active_control_parents, ancestors, zip_rows
from history_sources import separator_row
from run_workflow import prepare_source, session
from top_level import build_groups, resolve_top


def holders_from_csv(path, period):
    with path.open(encoding='utf-8-sig',newline='') as handle:
        reader=csv.DictReader(handle)
        reader.fieldnames=[k.strip().upper() for k in reader.fieldnames or []]
        rows=[]
        for row in reader:
            if separator_row(row): continue
            if None in row or any(v is None for v in row.values()):
                raise ValueError('Ragged historical holder record')
            rows.append({k:(None if k.startswith(('BHCK','BHDM','BHFN')) and v.strip() in ('.','NA','N/A') else v.strip())
                         for k,v in row.items()})
    for row in rows:
        row['RSSD9999']=row['RSSD9999'].replace('-','')
    validate_records(rows,'RSSD9001','RSSD9999',period)
    # LP/SP are retained for dated identity/country evidence, never used as consolidated finance.
    consolidated=[r for r in rows if r.get('BHCK2170') not in (None,'','.','NA')]
    return rows, consolidated


def mapped_flows(row, holder, mapping, affected):
    for name, code in mapping['ytd_fields'].items():
        current=as_int(holder.get(code))
        row[name+'_ytd']=current
        # Only Q1 is currently verified. Never infer quarterly figures in affected groups.
        row[name+'_quarter']=None if affected else current


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--period',required=True)
    parser.add_argument('--offline',action='store_true')
    parser.add_argument('--refresh',action='store_true')
    a=parser.parse_args(argv);root=a.root.resolve()
    mapping_path=root/'config'/('legacy_'+a.period+'.json')
    if not mapping_path.is_file():
        parser.error('No verified historical mapping for requested quarter')
    mapping=json.loads(mapping_path.read_text(encoding='utf-8'))
    if a.period!=mapping['period'] or a.period[4:]!='0331':
        parser.error('This bounded pilot supports its specified Q1 only')
    inventory=json.loads((root/'research/history/chicago_manifest.json').read_text(encoding='utf-8'))
    source=next((r for r in inventory['archives'] if r['family']=='holding_company' and r['period']==a.period and r.get('status')=='DOWNLOADED'),None)
    if not source or sha256(Path(source['snapshot']))!=source['sha256']:
        parser.error('Verified holder snapshot missing; run requested-range acquisition first')
    all_holders,holders=holders_from_csv(Path(source['snapshot']),a.period)
    countries={as_int(r['RSSD9001']):r.get('RSSD9005','') for r in all_holders}
    receipts=[source]
    with session() as client:
        for filename,kind,period in [(f'fdic_extended_{a.period}.json','fdic',a.period),
                                    ('CSV_RELATIONSHIPS.zip','CSV_RELATIONSHIPS.zip',None),
                                    ('CSV_TRANSFORMATIONS.zip','CSV_TRANSFORMATIONS.zip',None)]:
            receipts.append(prepare_source(root,client,filename,kind,period,offline=a.offline,refresh=a.refresh))
    bank_receipt,relation_receipt,event_receipt=receipts[1:]
    banks=load_fdic_json(Path(bank_receipt['snapshot']))
    validate_records(banks,'CERT','REPDTE',a.period)
    relations=list(zip_rows(Path(relation_receipt['snapshot'])))
    events=list(zip_rows(Path(event_receipt['snapshot'])))
    parents=active_control_parents(relations,a.period)
    core,ledger=build_groups(banks,holders,parents,a.period)
    bank_lookup={as_int(b['CERT']):b for b in banks}
    members_by_top=defaultdict(list)
    for link in ledger:
        if link['top_rssd'] is not None and link['bank_cert'] in bank_lookup:
            members_by_top[link['top_rssd']].append(bank_lookup[link['bank_cert']])
    current_holders={as_int(r['RSSD9001']):r for r in holders}
    changed=set()
    start=a.period[:4]+'0101'
    for event in events:
        if start<=event['DT_TRANS']<=a.period:
            changed.update(as_int(event[k]) for k in ('ID_RSSD_PREDECESSOR','ID_RSSD_SUCCESSOR'))
    for relation in relations:
        if relation['CTRL_IND']=='1' and relation['RELN_LVL']=='1' and any(start<=relation[k]<=a.period for k in ('DT_START','DT_END')):
            changed.update(as_int(relation[k]) for k in ('ID_RSSD_OFFSPRING','ID_RSSD_PARENT'))
    affected=set()
    for node in changed:
        resolved,_=resolve_top(node,parents)
        if resolved: affected.add(resolved)
    fields=json.loads((root/'config/public_columns.json').read_text(encoding='utf-8'))
    output,quarantine,checks=[],[],[]
    bank_ids={as_int(b['RSSDID']) for b in banks if b.get('RSSDID')}
    for original in core:
        top=original['top_rssd'];holder=current_holders.get(top)
        # Don't label a missing/foreign root as the verified highest US parent.
        domestic_holder=countries.get(top)=='UNITED STATES'
        candidate_bank=top in bank_ids and top not in countries
        if not domestic_holder and not candidate_bank:
            quarantine.append({'entity_key':original['entity_key'],'report_date':a.period,
                               'reason':'HIGHEST_US_ROOT_UNRESOLVED_OR_FOREIGN'})
            continue
        row=dict.fromkeys(fields)
        for key in ('entity_key','top_rssd','report_date','basis','bank_count','nested_bank_overlap'):
            row[key]=original[key]
        row.update(release_status='HISTORICAL_PARTIAL_REVIEW_REQUIRED',
                   coverage_note='March 2001 bounded mapping. Unverified historical financial fields withheld; see dictionary and coverage report.',
                   classification_status='DATED_US_HOLDER' if domestic_holder else 'BANK_NO_REPORTED_HOLDER_CANDIDATE',
                   primary_source='HISTORICAL_FR_Y9C' if holder else 'FDIC_BANK_ONLY',
                   flow_perimeter_review=top in affected)
        members=members_by_top[top]
        if holder:
            row['name']=holder.get('RSSD9017') or holder.get('RSSD9010')
            for name, code in mapping['stock_fields'].items(): row[name]=as_int(holder.get(code))
            values=[as_int(holder.get(c)) for c in mapping['deposit_components']]
            row['total_deposits']=None if any(v is None for v in values) else sum(values)
            mapped_flows(row,holder,mapping,top in affected)
        else:
            row['name']=next((b.get('NAMEHCR') or b.get('NAME') for b in members),'')
            for name in ('total_assets','total_equity','total_deposits','loans_net_allowances'):
                row[name]=original[name]
            # Bank-only YTD aggregate is not treated as consolidated BHC income.
        for name in ('DEP','DEPDOM','DEPFOR','DEPIDOM','DEPNIDOM'):
            row['bank_sum_'+name]=original['bank_sum_'+name]
        if row['interest_income_total_ytd'] is not None and row['interest_expense_total_ytd'] is not None and row['net_interest_income_ytd'] is not None:
            difference=row['interest_income_total_ytd']-row['interest_expense_total_ytd']-row['net_interest_income_ytd']
            checks.append({'entity_key':row['entity_key'],'report_date':a.period,'check':'NET_INTEREST_IDENTITY_YTD',
                           'status':'PASS' if difference==0 else 'FAIL','difference':difference})
        output.append(row)
    keys=[r['entity_key'] for r in output]
    if len(keys)!=len(set(keys)) or not output: raise ValueError('Empty or duplicate organisation output')
    folder=root/'outputs/legacy_financials'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:8])
    folder.mkdir(parents=True)
    write_csv(folder/'organisation_financials.csv',output,fields)
    write_csv(folder/'ownership_ledger.csv',ledger,list(ledger[0]))
    write_csv(folder/'validation.csv',checks,['entity_key','report_date','check','status','difference'])
    write_csv(folder/'quarantine.csv',quarantine,['entity_key','report_date','reason'])
    coverage=[{'column':f,'available_rows':sum(r[f] is not None for r in output),
               'blank_rows':sum(r[f] is None for r in output),'note':'Blank may mean unverified mapping, not reported or withheld; never zero'} for f in fields]
    write_csv(folder/'measure_coverage.csv',coverage,list(coverage[0]))
    known={name:code for name,code in mapping['stock_fields'].items()}
    for name,code in mapping['ytd_fields'].items():
        known[name+'_ytd']=code;known[name+'_quarter']=code
    known['total_deposits']='+'.join(mapping['deposit_components'])
    dictionary=[]
    metadata={'entity_key','top_rssd','report_date','basis','bank_count','release_status','coverage_note',
              'nested_bank_overlap','name','flow_perimeter_review','classification_status','primary_source'}
    for field in fields:
        dictionary.append({'column':field,'source_code':known.get(field,''),
                           'measurement':'metadata' if field in metadata else 'YTD_flow' if field.endswith('_ytd') else 'quarter_flow' if field.endswith('_quarter') else 'stock',
                           'unit':'' if field in metadata else 'USD_thousands',
                           'period':a.period,'mapping_status':'VERIFIED_BOUNDED' if field in known else 'METADATA' if field in metadata else 'SEE_COVERAGE_UNVERIFIED_OR_BANK_SOURCE',
                           'missingness':'Blank is unreported, withheld or unverified; not zero',
                           'reference':mapping['source_form'] if field in known else 'See source receipts and measure_coverage.csv'})
    write_csv(folder/'data_dictionary.csv',dictionary,list(dictionary[0]))
    (folder/'data_dictionary.json').write_text(json.dumps(mapping,indent=2),encoding='utf-8')
    report={'processing_status':'COMPLETED','release_status':'HISTORICAL_PARTIAL_REVIEW_REQUIRED','period':a.period,
            'organisation_quarters':len(output),'columns':len(fields),'input_banks':len(banks),
            'input_holder_records':len(all_holders),'consolidated_y9c_filers':len(holders),
            'basis_counts':dict(Counter(r['basis'] for r in output)),'duplicate_keys':0,
            'unresolved_ownership':sum(r['top_rssd'] is None for r in ledger),
            'quarantined_groups':len(quarantine),'failed_accounting_checks':sum(r['status']=='FAIL' for r in checks),
            'checks_performed':len(checks),'source_errors':[],'sources':receipts,'mapping_sha256':sha256(mapping_path),
            'current_mvp_complete':False,'limitations':mapping['limitations'],
            'not_yet_verified':['Detailed historical field mappings','All institution-type classification','Independent reference-filing acceptance'],
            'finished_at_utc':datetime.now(timezone.utc).isoformat()}
    (folder/'release_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'output':str(folder),**{k:v for k,v in report.items() if k not in ('sources','limitations','not_yet_verified')}},indent=2))
    return 2


if __name__=='__main__': raise SystemExit(main())
