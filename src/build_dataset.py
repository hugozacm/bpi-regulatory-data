"""Integrated, bounded research dataset. Exit 2 means release is blocked."""
from __future__ import annotations

import argparse
import json
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import duckdb
import requests

from bpi_pipeline import (FDIC_FIELDS, Y9_FIELDS, as_int, load_fdic_json, load_y9,
                          quarter_from_ytd, sha256, validate_records, write_csv)
from history_audit import active_control_parents, zip_rows
from run_workflow import (STRUCTURE_FIELDS, fdic_params, prepare_source, previous_quarter,
                          session, utc_now, validate_source, failure_reason)
from top_level import build_groups, resolve_top, strict_sum
from release_mvp import apply_delivery_quality
from output_dictionary import build_dictionary


def quarters(start, end):
    previous_quarter(start)
    previous_quarter(end)
    if start > end:
        raise ValueError('Start is after end')
    return [f'{year}{suffix}' for year in range(int(start[:4]), int(end[:4]) + 1)
            for suffix in ('0331', '0630', '0930', '1231') if start <= f'{year}{suffix}' <= end]


def needed_periods(periods):
    return sorted(set(periods) | {previous_quarter(p) for p in periods if p[4:6] != '03'})


def plan_period_delivery(periods, available, detailed):
    """Never manufacture a missing quarter; prior gaps withhold flows, not stocks."""
    result=[]
    for q in periods:
        if q not in available:
            result.append({'report_date':q,'status':'MISSING','reason':'CURRENT_Y9C_OR_CALL_REPORT_SOURCE_UNAVAILABLE'})
            continue
        reasons=[]
        if q[4:6]!='03' and previous_quarter(q) not in available:
            reasons.append('PRIOR_QUARTER_UNAVAILABLE_QUARTERLY_FLOWS_WITHHELD')
        if q not in detailed:reasons.append('DETAILED_BANK_SCHEDULE_UNAVAILABLE_CORE_ONLY')
        result.append({'report_date':q,'status':'DELIVERED_WITH_LIMITATIONS' if reasons else 'DELIVERED',
                       'reason':';'.join(reasons)})
    return result


def safe_flow(period, current, previous, stable, event):
    if not stable or event:
        return None, 'MEMBERSHIP_OR_EVENT_REVIEW'
    value = quarter_from_ytd(period, current, previous)
    return value, 'AVAILABLE' if value is not None else 'MISSING_CURRENT_OR_PRIOR'


def bank_flow(period, members, previous, field, stable, event):
    if not stable or event:
        return None, 'MEMBERSHIP_OR_EVENT_REVIEW'
    values = []
    for member in members:
        current = as_int(member.get(field))
        old = previous.get(as_int(member['CERT']), {})
        value = quarter_from_ytd(period, current, old.get(field))
        if value is None:
            return None, 'MISSING_CURRENT_OR_PRIOR'
        if field == 'NETINC' and as_int(member.get('NETINCQ')) != value:
            return None, 'FDIC_QUARTERLY_INCOME_DISAGREEMENT'
        values.append(value)
    return (sum(values), 'AVAILABLE') if values else (None, 'NO_BANK_MEMBERS')


def download_extended(client, root, period, fields, refresh=False):
    """Dedicated expanded responses, never overwrite core source responses."""
    name = f'fdic_schedules_{period}.json'
    receipt = root / 'research' / 'download_cache' / (name + '.receipt.json')
    if receipt.exists() and not refresh:
        record = json.loads(receipt.read_text(encoding='utf-8'))
        snapshot = Path(record['snapshot'])
        if sha256(snapshot) != record['sha256']:
            raise ValueError('Expanded cached source hash mismatch')
        rows = load_fdic_json(snapshot)
        validate_records(rows, 'CERT', 'REPDTE', period)
        if all(set(fields) <= set(row) for row in rows):
            record['acquisition'] = 'REUSED_EXPANDED_SNAPSHOT'
            return record
    params = fdic_params(period)
    params['fields'] = ','.join(fields)
    from run_workflow import check_access
    response = client.get('https://api.fdic.gov/banks/financials', params=params, timeout=(15, 45))
    check_access(response)
    staging = root / 'research' / 'download_cache'
    staging.mkdir(parents=True, exist_ok=True)
    path = staging / (uuid4().hex + '.part')
    try:
        with path.open('xb') as handle:
            handle.write(response.content)
        validate_source(path, 'fdic', period)
        rows = load_fdic_json(path)
        if any(not set(fields) <= set(row) for row in rows):
            raise ValueError('Expanded FDIC response is missing requested field keys')
        digest = sha256(path)
        snapshot = root / 'research' / 'snapshots' / digest / name
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        if snapshot.exists():
            if sha256(snapshot) != digest:
                raise ValueError('Modified expanded source snapshot')
        else:
            with snapshot.open('xb') as handle:
                handle.write(response.content)
        record = {'filename': name, 'period': period, 'status': 'READY', 'snapshot': str(snapshot.resolve()),
                'sha256': digest, 'source_url': response.url, 'request_parameters': params,
                'retrieved_at_utc': utc_now(), 'acquisition': 'DOWNLOADED'}
        receipt.write_text(json.dumps(record, indent=2), encoding='utf-8')
        return record
    finally:
        path.unlink(missing_ok=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--start', default='20230331')
    p.add_argument('--end', default='20260630')
    p.add_argument('--output', type=Path, help='Unique new run directory directly under outputs/dataset')
    p.add_argument('--offline', action='store_true')
    p.add_argument('--refresh', action='store_true')
    p.add_argument('--progress-file', type=Path, help='Local progress receipt for the bounded frontend worker')
    p.add_argument('--browser-source-dir', type=Path)
    p.add_argument('--source-manifest', type=Path, help='Replay source snapshots from a previous release_report.json; requires --offline')
    a = p.parse_args(argv)
    progress_events=[]
    def progress(stage, message, **details):
        if a.progress_file:
            if not progress_events or progress_events[-1]['stage']!=stage:
                progress_events.append({'stage':stage,'at':utc_now()})
            a.progress_file.parent.mkdir(parents=True,exist_ok=True)
            temporary=a.progress_file.with_suffix('.tmp')
            temporary.write_text(json.dumps({'stage':stage,'message':message,'updated_at_utc':utc_now(),'events':progress_events,**details}),encoding='utf-8')
            temporary.replace(a.progress_file)
    progress('CHECKING_SOURCES','Checking saved sources; only missing inputs will be downloaded')
    if a.offline and a.refresh:
        p.error('offline and refresh are mutually exclusive')
    if a.source_manifest and not a.offline:
        p.error('source-manifest replay requires --offline')
    periods = quarters(a.start, a.end)
    root = a.root.resolve()
    mapping_path = root / 'config' / 'expanded_measures.json'
    mapping = json.loads(mapping_path.read_text(encoding='utf-8'))
    fields = mapping['fields']
    if any(a.start < f['valid_from'] or a.end > f['valid_to'] for f in fields):
        p.error('Requested dates exceed verified mapping bounds; add period-specific mappings first')
    output_root=root/'outputs/dataset'
    out=a.output.resolve() if a.output else output_root/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:8])
    if out.parent!=output_root:
        p.error('Output must be a new directory directly under outputs/dataset')
    out.mkdir(parents=True, exist_ok=False)
    report = {'started_at_utc': utc_now(), 'requested_start': a.start, 'requested_end': a.end,
              'release_status': 'BLOCKED_REVIEW_REQUIRED', 'sources': [], 'source_errors': [],
              'mapping_sha256': sha256(mapping_path), 'output': str(out),
              'historical_scope_complete': False, 'approved_final_dataset': False}
    (out / 'measure_dictionary.json').write_text(json.dumps(mapping, indent=2), encoding='utf-8')

    def save_report():
        (out / 'release_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')

    paths = {}
    replay = {}
    if a.source_manifest:
        original = json.loads(a.source_manifest.read_text(encoding='utf-8'))
        if original['mapping_sha256'] != sha256(mapping_path):
            p.error('Replay mapping hash differs; use the original version of the mapping')
        replay = {record['filename']: record for record in original['sources']}
    with session() as client:
        specs = [(f'BHCF{q}.ZIP', 'y9', q) for q in needed_periods(periods)]
        specs += [(f'fdic_extended_{q}.json', 'fdic', q) for q in needed_periods(periods)]
        specs += [(name, name, None) for name in STRUCTURE_FIELDS]
        for name, kind, q in specs:
            progress('DOWNLOADING','Checking cache / acquiring '+name,completed_sources=len(report['sources']),total_sources=len(specs))
            try:
                if replay:
                    record = dict(replay[name])
                    if sha256(Path(record['snapshot'])) != record['sha256']:
                        raise ValueError('Replay source hash mismatch')
                    validate_source(Path(record['snapshot']), kind, q)
                    record['acquisition'] = 'REPLAYED_SNAPSHOT'
                else:
                    record = prepare_source(root, client, name, kind, q, a.offline, a.refresh, a.browser_source_dir)
                paths[name] = Path(record['snapshot'])
                report['sources'].append(record)
            except (ValueError, OSError, KeyError, requests.RequestException, zipfile.BadZipFile) as error:
                report['source_errors'].append({'filename': name, 'reason': failure_reason(error), 'error': str(error)[:500]})
            save_report()
        if any(name not in paths for name in STRUCTURE_FIELDS):
            report['processing_status'] = 'BLOCKED_INPUTS'
            report['period_coverage']=[{'report_date':q,'status':'MISSING','reason':'REQUIRED_OWNERSHIP_OR_EVENT_SOURCE_UNAVAILABLE'} for q in periods]
            report['missing_periods']=periods
            write_csv(out/'period_coverage.csv',report['period_coverage'],['report_date','status','reason'])
            save_report()
            print(json.dumps(report, indent=2))
            return 1
        bank_fields = sorted(set(FDIC_FIELDS) | {f['fdic'] for f in fields if f['fdic']})
        if replay:
            for q in needed_periods(periods):
                name = f'fdic_schedules_{q}.json'
                if name in replay:
                    try:
                        record = dict(replay[name])
                        if sha256(Path(record['snapshot'])) != record['sha256']:
                            raise ValueError('Expanded replay source hash mismatch')
                        validate_source(Path(record['snapshot']), 'fdic', q)
                        record['acquisition'] = 'REPLAYED_SNAPSHOT'
                        paths[f'fdic_extended_{q}.json'] = Path(record['snapshot'])
                        report['sources'].append(record)
                    except (ValueError,OSError,KeyError) as error:
                        report['source_errors'].append({'filename':name,'reason':failure_reason(error),'error':str(error)[:500]})
        if not a.offline:
            for q in needed_periods(periods):
                try:
                    progress('DOWNLOADING','Checking expanded bank schedules for '+q)
                    record = download_extended(client, root, q, bank_fields, a.refresh)
                    paths[f'fdic_extended_{q}.json'] = Path(record['snapshot'])
                    report['sources'].append(record)
                except (ValueError, OSError, KeyError, requests.RequestException) as error:
                    # Retain core financials, but the release gate records the gap.
                    report['source_errors'].append({'filename': f'fdic_schedules_{q}.json', 'error': str(error)[:500]})
                save_report()

    relations = list(zip_rows(paths['CSV_RELATIONSHIPS.zip']))
    events = list(zip_rows(paths['CSV_TRANSFORMATIONS.zip']))
    extra_fields = list(dict.fromkeys(Y9_FIELDS + ['RSSD9017', 'RSSD9010'] + [f['field'] for f in fields]))
    all_rows, all_ledger, checks, coverage = [], [], [], []
    period_cache = {}

    def data(q):
        if q not in period_cache:
            banks = load_fdic_json(paths[f'fdic_extended_{q}.json'])
            holders = load_y9(paths[f'BHCF{q}.ZIP'], fields=extra_fields)
            validate_records(banks, 'CERT', 'REPDTE', q)
            validate_records(holders, 'RSSD9001', 'RSSD9999', q)
            period_cache[q] = banks, holders, active_control_parents(relations, q)
        return period_cache[q]

    available=set()
    for q in needed_periods(periods):
        if f'fdic_extended_{q}.json' not in paths or f'BHCF{q}.ZIP' not in paths:continue
        try:
            data(q)
            available.add(q)
        except (ValueError,OSError,KeyError,zipfile.BadZipFile) as error:
            report['source_errors'].append({'filename':'financial_inputs_'+q,'reason':failure_reason(error),'error':str(error)[:500]})
    requested_periods=list(periods)
    detailed={s.get('period') for s in report['sources'] if s['filename'].startswith('fdic_schedules_') and s.get('period') in available}
    period_coverage=plan_period_delivery(periods,available,detailed)
    for item in period_coverage:
        if item['status']!='MISSING' and any(item['report_date'] in s['filename'] for s in report['source_errors']):
            item['status']='DELIVERED_WITH_LIMITATIONS'
            item['reason']=';'.join(filter(None,[item['reason'],'SOURCE_ACQUISITION_WARNING_REVIEW_PROVENANCE']))
    report.update(requested_periods=requested_periods,period_coverage=period_coverage,
                  delivered_periods=[r['report_date'] for r in period_coverage if r['status']!='MISSING'],
                  missing_periods=[r['report_date'] for r in period_coverage if r['status']=='MISSING'])
    write_csv(out/'period_coverage.csv',period_coverage,['report_date','status','reason'])
    periods=report['delivered_periods']
    if not periods:
        report['processing_status']='BLOCKED_INPUTS';save_report();return 1
    for q in periods:
        progress('PROCESSING','Building institutions and financial measures for '+q,period=q)
        banks, holders, parents = data(q)
        prior = previous_quarter(q)
        old_banks, old_holders, old_parents = data(prior) if q[4:6] != '03' and prior in available else ([], [], {})
        core, ledger = build_groups(banks, holders, parents, q, old_banks, old_holders)
        members = defaultdict(list)
        bank_by_cert = {as_int(b['CERT']): b for b in banks}
        for link in ledger:
            if link['bank_cert'] and link['top_rssd']:
                members[link['top_rssd']].append(bank_by_cert[link['bank_cert']])
        previous_members = defaultdict(set)
        for bank in old_banks:
            top, _ = resolve_top(as_int(bank.get('RSSDID')), old_parents)
            if top:
                previous_members[top].add(as_int(bank['CERT']))
        current_holders = {as_int(h['RSSD9001']): h for h in holders}
        prev_holders = {as_int(h['RSSD9001']): h for h in old_holders}
        prev_banks = {as_int(b['CERT']): b for b in old_banks}
        from calendar import monthrange
        month = ((int(q[4:6]) - 1) // 3) * 3 + 1
        quarter_start = f'{q[:4]}{month:02d}01'
        affected = set()
        # Consider transformations of descendant entities as well as the root.
        for event in events:
            if quarter_start <= event['DT_TRANS'] <= q:
                for key in ('ID_RSSD_PREDECESSOR', 'ID_RSSD_SUCCESSOR'):
                    rssd = as_int(event[key])
                    for graph in (parents, old_parents):
                        top, _ = resolve_top(rssd, graph)
                        if top:
                            affected.add(top)
        counts = Counter()
        changed_nodes = set()
        for relation in relations:
            if relation['CTRL_IND'] == '1' and relation['RELN_LVL'] == '1' and (
                quarter_start <= relation['DT_START'] <= q or quarter_start <= relation['DT_END'] <= q
            ):
                changed_nodes.update((as_int(relation['ID_RSSD_OFFSPRING']), as_int(relation['ID_RSSD_PARENT'])))
        for row in core:
            top = row['top_rssd']
            holder = current_holders.get(top)
            member = members[top]
            stable = q[4:6] == '03' or {as_int(b['CERT']) for b in member} == previous_members[top]
            # A control change on the path is also a perimeter change.
            from history_audit import ancestors
            node_ids = {top} | {as_int(b.get('RSSDID')) for b in member}
            for b in member:
                node_ids.update(ancestors(as_int(b.get('RSSDID')), parents))
            control_change = bool(node_ids & changed_nodes)
            event = top in affected or control_change
            row.update(name=holder.get('RSSD9017', '') if holder else next((b.get('NAMEHCR') for b in member if as_int(b.get('RSSDHCR')) == top and b.get('NAMEHCR')), member[0].get('NAME', '') if len(member) == 1 else ''),
                       flow_perimeter_review=event or not stable,
                       classification_status='NOT_INDEPENDENTLY_VERIFIED',
                       bank_count=len(member), primary_source='FR_Y9C' if holder else 'FDIC_BANK_ONLY')
            for f in fields:
                name, code = f['name'], f['field']
                if holder:
                    value = as_int(holder.get(code))
                    status = 'AVAILABLE' if value is not None else 'NOT_REPORTED_OR_UNAVAILABLE'
                    if f['type'] == 'stock':
                        row[name] = value
                    else:
                        row[name + '_ytd'] = value
                        value_q = quarter_from_ytd(q, value, prev_holders.get(top, {}).get(code))
                        # Preserve reported perimeter flows; require review around changes.
                        row[name + '_quarter'] = value_q
                        if value_q is None:
                            status = 'MISSING_CURRENT_OR_PRIOR'
                elif f['fdic'] and not row['nested_bank_overlap']:
                    value = strict_sum(member, f['fdic'])
                    row[name + '_ytd'] = None  # do not label current-member YTD as historical group YTD
                    value_q, status = bank_flow(q, member, prev_banks, f['fdic'], stable, event)
                    row[name + '_quarter'] = value_q
                else:
                    status = 'NO_VERIFIED_BANK_MAPPING' if not f['fdic'] else 'NESTED_BANK_OVERLAP'
                    if f['type'] == 'stock':
                        row[name] = None
                    else:
                        row[name + '_ytd'] = None
                        row[name + '_quarter'] = None
                counts[(name, status)] += 1
            if holder:
                # Explicit holding-company equity differs from total equity/perimeter variants.
                row['total_equity'] = row.get('holding_company_equity')
            else:
                row['net_income_quarter'] = row.get('net_income_parent_quarter')
            for suffix in ('_ytd', '_quarter'):
                values = [row.get(n + suffix) for n in ('interest_income_total', 'interest_expense_total', 'net_interest_income')]
                if None not in values:
                    difference = values[0] - values[1] - values[2]
                    checks.append({'report_date': q, 'entity_key': row['entity_key'], 'check': 'NET_INTEREST_IDENTITY' + suffix,
                                   'status': 'PASS' if difference == 0 else 'FAIL', 'difference': difference})
            all_rows.append(row)
        all_ledger.extend(ledger)
        coverage.extend({'report_date': q, 'measure': name, 'status': status, 'count': count} for (name, status), count in sorted(counts.items()))
        print(f'{q}: {len(core)} organisation rows', flush=True)

    progress('VALIDATING','Checking unique keys, ownership gaps and accounting identities')
    raw_rows = all_rows
    all_rows, quarantine, input_checks, checks, withheld = apply_delivery_quality(raw_rows)
    keys = [(r['entity_key'], r['report_date']) for r in all_rows]
    duplicates = len(keys) - len(set(keys))
    unresolved = sum(r['top_rssd'] is None for r in all_ledger)
    failures = sum(c['status'] == 'FAIL' for c in checks)
    tables = {'organisation_financials': all_rows, 'ownership_ledger': all_ledger, 'validation': checks,
              'validation_input': input_checks, 'measure_coverage': coverage,
              'raw_organisation_financials': raw_rows, 'financial_quarantine': quarantine}
    # An empty quarantine is still a downloadable, header-only evidence file.
    if not quarantine:
        write_csv(out/'financial_quarantine.csv', [], list(raw_rows[0]))
    output_columns=list(raw_rows[0])
    (out/'output_dictionary.json').write_text(json.dumps({'schema_version':'OUTPUT_DICTIONARY_V1',
        'column_count':len(output_columns),'columns':build_dictionary(output_columns,mapping),
        'sources':mapping.get('sources',[])},indent=2),encoding='utf-8')
    progress('EXPORTING','Writing the CSV, coverage and validation outputs')
    with duckdb.connect(str(out / 'dataset.duckdb')) as con:
        for name, rows in tables.items():
            if not rows:
                continue
            columns = list(dict.fromkeys(key for row in rows for key in row))
            write_csv(out / (name + '.csv'), rows, columns)
            if name in ('organisation_financials', 'raw_organisation_financials', 'financial_quarantine'):
                text = {'entity_key', 'report_date', 'basis', 'release_status', 'coverage_note', 'name', 'classification_status', 'primary_source'}
                boolean = {'nested_bank_overlap', 'flow_perimeter_review'}
                types = {col: 'VARCHAR' if col in text else 'BOOLEAN' if col in boolean else 'BIGINT' for col in columns}
                con.execute(f'CREATE TABLE {name} AS SELECT * FROM read_csv(?, header=true, columns=?)', [str(out / (name + '.csv')), types])
            else:
                con.execute(f'CREATE TABLE {name} AS SELECT * FROM read_csv_auto(?, header=true, sample_size=-1)', [str(out / (name + '.csv'))])
            con.execute(f'COPY {name} TO ? (FORMAT PARQUET, COMPRESSION ZSTD)', [str(out / (name + '.parquet'))])
    report.update(processing_status='PARTIAL' if any(r['status']!='DELIVERED' for r in period_coverage) or report['source_errors'] else 'COMPLETED', finished_at_utc=utc_now(), quarters=len(periods),
                  organisation_quarters=len(all_rows), duplicate_keys=duplicates, unresolved_ownership=unresolved,
                  failed_accounting_checks=failures, schedule_fields=len(fields),
                  quality_policy='CAUTIOUS_FLOW_AND_COMPONENT_CHECKS_V1',
                  upstream_organisation_quarters=len(raw_rows), financial_rows_quarantined=len(quarantine),
                  input_failed_accounting_checks=sum(c['status']=='FAIL' for c in input_checks),
                  accounting_checks_passed=sum(c['status']=='PASS' for c in checks),
                  accounting_checks_not_testable=sum(c['status'].startswith('NOT_TESTABLE') for c in checks),
                  uncertain_quarter_values_withheld=withheld,
                  release_blockers=['Historical coverage not extended to maximum available',
                     'Institution types and foreign ultimate-parent scope not fully verified',
                     'Detailed Call Report equivalents not all mapped',
                     'Missing/reporting-threshold eligibility and source amendments need review',
                     'Perimeter/merger-quarter income and consolidated-vs-bank-only comparability need review',
                     'Independent reference-filing acceptance checks incomplete'])
    save_report()
    lines = ['# Dataset release report', '', 'Status: BLOCKED_REVIEW_REQUIRED',
             f'Quarters: {len(periods)}; organisation-quarter rows: {len(all_rows)}; mapped schedule fields: {len(fields)}',
             f'Duplicate keys: {duplicates}; unresolved ownership records: {unresolved}; failed accounting checks: {failures}',
             f'Input check failures: {report["input_failed_accounting_checks"]}; quarantined rows: {len(quarantine)}; uncertain quarterly values withheld: {withheld}',
             'validation.csv covers delivered rows; validation_input.csv retains checks on the original rows. Missing-input checks are not passes.',
             '', '## Blocks to a final research release', ''] + ['- ' + b for b in report['release_blockers']]
    (out / 'release_report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (out / 'REVIEW_REQUIRED.txt').write_text('Not an approved final dataset. See release_report.md.\n', encoding='utf-8')
    print(out)
    progress('COMPLETED_REVIEW_REQUIRED','Build finished; review validation and coverage before research use')
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
