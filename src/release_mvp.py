"""Freeze MVP v1 under explicit assumptions, without certifying a full research release."""
import argparse
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import duckdb

from bpi_pipeline import sha256, write_csv
from top_level import resolve_top
from history_audit import active_control_parents, zip_rows


EXPECTED_PERIODS = [f'{y}{q}' for y in range(2023, 2027) for q in ('0331', '0630', '0930', '1231')
                    if f'{y}{q}' <= '20260630']


def freeze_flows(row):
    """Retain reported YTD evidence, but never publish uncertain quarter flows."""
    row = dict(row)
    changed = 0
    if row.get('flow_perimeter_review'):
        for name in row:
            if name.endswith('_quarter') and row[name] is not None:
                row[name] = None
                changed += 1
    row['release_status'] = 'MVP_V1_RESEARCH_DRAFT'
    return row, changed


def accounting_checks(row):
    definitions = {
        'NET_INTEREST': ('net_interest_income', ['interest_income_total', '-interest_expense_total']),
        'INTEREST_INCOME_COMPONENTS': ('interest_income_total', [
            'interest_loans_residential', 'interest_loans_other_real_estate', 'interest_loans_other',
            'interest_loans_foreign', 'lease_income', 'interest_depository_balances', 'interest_treasury_agency',
            'interest_mbs', 'interest_other_securities', 'interest_trading_assets', 'interest_fed_funds_repos', 'interest_other']),
        'INTEREST_EXPENSE_COMPONENTS': ('interest_expense_total', [
            'interest_expense_small_time_deposits', 'interest_expense_large_time_deposits',
            'interest_expense_other_domestic_deposits', 'interest_expense_foreign_deposits',
            'interest_expense_fed_funds_repos', 'interest_expense_trading_borrowings',
            'interest_expense_subordinated', 'interest_expense_other']),
        'TRADING_REVENUE_COMPONENTS': ('trading_revenue', [
            'trading_interest_rate', 'trading_fx', 'trading_equity', 'trading_commodity_other', 'trading_credit']),
    }
    result = []
    for suffix in ('_ytd', '_quarter'):
        for check, (total, parts) in definitions.items():
            values = [row.get(name.lstrip('-') + suffix) for name in parts]
            target = row.get(total + suffix)
            difference = None if target is None or None in values else sum(
                (-value if name.startswith('-') else value) for name, value in zip(parts, values)) - target
            result.append({'entity_key': row['entity_key'], 'report_date': row['report_date'],
                           'check': check + suffix, 'difference': difference,
                           'status': 'NOT_TESTABLE_MISSING_INPUT' if difference is None else 'PASS' if difference == 0 else 'FAIL'})
    return result


def export_table(con, name, path):
    con.execute(f'COPY {name} TO ? (HEADER, DELIMITER \',\')', [str(path / (name + '.csv'))])
    con.execute(f'COPY {name} TO ? (FORMAT PARQUET, COMPRESSION ZSTD)', [str(path / (name + '.parquet'))])


def quarantine_conflicts(rows, checks):
    failed = {(c['entity_key'], str(c['report_date'])) for c in checks if c['status'] == 'FAIL'}
    bad = [r for r in rows if (r['entity_key'], str(r['report_date'])) in failed]
    good = [r for r in rows if (r['entity_key'], str(r['report_date'])) not in failed]
    return good, bad


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True, help='Completed integrated dataset directory')
    p.add_argument('--output', type=Path)
    a = p.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    source = a.input.resolve()
    upstream = json.loads((source / 'release_report.json').read_text(encoding='utf-8'))
    if upstream.get('processing_status') != 'COMPLETED' or upstream.get('source_errors'):
        raise ValueError('MVP requires a completed build without source acquisition errors')
    source_checks = []
    for record in upstream['sources']:
        valid = sha256(Path(record['snapshot'])) == record['sha256']
        source_checks.append({'filename': record['filename'], 'hash_matches': valid})
    if not all(record['hash_matches'] for record in source_checks):
        raise ValueError('Source snapshot hash mismatch')
    mapping_path = root / 'config' / 'expanded_measures.json'
    if sha256(mapping_path) != upstream['mapping_sha256']:
        raise ValueError('Mapping version differs from the upstream build')
    out = a.output or root / 'outputs' / 'mvp_v1' / (
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8])
    out.mkdir(parents=True, exist_ok=False)
    with duckdb.connect(str(source / 'dataset.duckdb'), read_only=True) as original:
        cols = [d[0] for d in original.execute('SELECT * FROM organisation_financials LIMIT 0').description]
        raw_rows = [dict(zip(cols, values)) for values in original.execute('SELECT * FROM organisation_financials ORDER BY report_date,entity_key').fetchall()]
        ledger_cols = [d[0] for d in original.execute('SELECT * FROM ownership_ledger LIMIT 0').description]
        ledger = [dict(zip(ledger_cols, values)) for values in original.execute('SELECT * FROM ownership_ledger').fetchall()]
    relations_path = next(Path(s['snapshot']) for s in upstream['sources'] if s['filename'] == 'CSV_RELATIONSHIPS.zip')
    relations = list(zip_rows(relations_path))
    graph = {q: active_control_parents(relations, q) for q in EXPECTED_PERIODS}
    impacted = set()
    exceptions = []
    for link in ledger:
        if link['top_rssd'] is None:
            q = str(link['report_date'])
            top, _ = resolve_top(link['reported_holder_rssd'], graph[q])
            if top:
                impacted.add((int(top), q))
            exceptions.append({'record_type': 'UNRESOLVED_OWNERSHIP', 'entity_key': '', 'report_date': q,
                               'bank_cert': link['bank_cert'], 'reason': link['ownership_status']})
    rows, suppressed, deposits_suppressed, removed = [], 0, 0, 0
    for raw in raw_rows:
        q = str(raw['report_date'])
        if (int(raw['top_rssd']), q) in impacted:
            if raw['basis'] == 'BANK_ONLY_AGGREGATE':
                removed += 1
                exceptions.append({'record_type': 'EXCLUDED_GROUP', 'entity_key': raw['entity_key'], 'report_date': q,
                                   'bank_cert': None, 'reason': 'UNRESOLVED_MEMBER_COULD_MAKE_BANK_SUM_INCOMPLETE'})
                continue
            # Consolidated financials remain valid as reported, but bank detail
            # is not presented as complete when a member could not be assigned.
            for name in raw:
                if name.startswith('bank_sum_') or name == 'bank_member_net_income_ytd':
                    raw[name] = None
            deposits_suppressed += 1
            exceptions.append({'record_type': 'BANK_DETAIL_WITHHELD', 'entity_key': raw['entity_key'], 'report_date': q,
                               'bank_cert': None, 'reason': 'UNRESOLVED_MEMBER_COULD_MAKE_BANK_DETAIL_INCOMPLETE'})
        row, count = freeze_flows(raw)
        suppressed += count
        rows.append(row)
    periods = sorted({str(r['report_date']) for r in rows})
    if periods != EXPECTED_PERIODS:
        raise ValueError('MVP period range is not exactly 2023Q1–2026Q2')
    duplicates = len(rows) - len({(r['entity_key'], r['report_date']) for r in rows})
    checks = [check for row in rows for check in accounting_checks(row)]
    rows, financial_quarantine = quarantine_conflicts(rows, checks)
    for row in financial_quarantine:
        exceptions.append({'record_type': 'EXCLUDED_FINANCIAL_CONFLICT', 'entity_key': row['entity_key'],
                           'report_date': row['report_date'], 'bank_cert': None,
                           'reason': 'FAILED_EXACT_ACCOUNTING_IDENTITY; see financial_tests.csv and financial_quarantine.csv'})
    main_checks = [check for row in rows for check in accounting_checks(row)]
    if sorted({str(r['report_date']) for r in rows}) != EXPECTED_PERIODS:
        raise ValueError('Financial quarantine removed an entire required reporting quarter')
    failures = sum(c['status'] == 'FAIL' for c in main_checks)
    passed = sum(c['status'] == 'PASS' for c in main_checks)
    not_testable = sum(c['status'].startswith('NOT_TESTABLE') for c in main_checks)
    accepted = duplicates == 0 and failures == 0 and passed > 0
    dictionary = json.loads(mapping_path.read_text(encoding='utf-8'))
    derived = {}
    for field in dictionary['fields']:
        for name in ([field['name']] if field['type'] == 'stock' else [field['name'] + '_ytd', field['name'] + '_quarter']):
            derived[name] = field
    dictionary_rows = []
    core_fields = {
        'total_assets': ('BHCK2170 / ASSET', 'Quarter-end total assets; source basis identifies the reporting perimeter'),
        'total_equity': ('BHCT3210 / EQ', 'Y-9C holding-company equity or bank-reported equity; not fully harmonised'),
        'total_loans': ('BHCK2122', 'Y-9C loans net of unearned income; not populated from bank net-allowance loans'),
        'loans_net_allowances': ('LNLSNET', 'FDIC bank loans net of allowances; separate definition'),
        'total_deposits': ('BHDM6631+BHDM6636+BHFN6631+BHFN6636 / DEP', 'Strict component sum or FDIC bank aggregate'),
        'net_income_ytd': ('BHCK4340', 'Reported holder YTD; bank-only historical YTD withheld'),
        'net_income_quarter': ('BHCK4340 / NETINC', 'Q1 direct or adjacent YTD difference; uncertain quarter flows withheld'),
        'bank_member_net_income_ytd': ('NETINC', 'Current members YTD evidence; not historical group YTD'),
        'top_rssd': ('NIC ID_RSSD_PARENT / ID_RSSD_OFFSPRING', 'Highest dated control root; not independently verified institution classification'),
        'entity_key': ('TOP_RSSD_<top_rssd>', 'Stable root identifier, not a retroactive merger identifier'),
        'report_date': ('RSSD9999 / REPDTE', 'Quarter-end date YYYYMMDD'),
        'bank_count': ('Ownership ledger', 'Number of assigned bank records; not proof of complete group membership'),
        'basis': ('Pipeline selection', 'CONSOLIDATED_Y9C or BANK_ONLY_AGGREGATE; independent candidates use the latter basis'),
        'name': ('RSSD9017 / NAMEHCR / NAME', 'May be absent when no verified root name is available'),
        'release_status': ('MVP packaging', 'MVP_V1_RESEARCH_DRAFT; not financial certification'),
        'coverage_note': ('Pipeline review', 'Reporting perimeter and classification limitations'),
        'nested_bank_overlap': ('Dated NIC graph', 'Nested reporting banks detected; aggregate bank values withheld'),
        'flow_perimeter_review': ('NIC control dates and transformations', 'Uncertain quarter flows withheld in MVP; reported YTD evidence retained'),
        'classification_status': ('Pipeline review', 'Institution types not independently verified'),
        'primary_source': ('Pipeline selection', 'FR_Y9C or FDIC_BANK_ONLY'),
    }
    for field in ('DEP', 'DEPDOM', 'DEPFOR', 'DEPIDOM', 'DEPNIDOM'):
        core_fields['bank_sum_' + field] = (field, 'Strict matched-bank-perimeter sum; separate from consolidated deposits')
    for name in cols:
        f = derived.get(name, {})
        dictionary_rows.append({'column': name, 'unit': 'USD_thousands' if name in derived or name in {
            'total_assets', 'total_equity', 'total_loans', 'loans_net_allowances', 'total_deposits',
            'net_income_ytd', 'net_income_quarter', 'bank_member_net_income_ytd'} or name.startswith('bank_sum_') else 'metadata',
            'source_field': f.get('field', core_fields.get(name, ('', ''))[0]), 'fdic_equivalent': f.get('fdic') or '',
            'schedule': f.get('schedule', ''), 'item': f.get('item', ''),
            'measurement': 'quarterly_flow' if name.endswith('_quarter') else f.get('type',
                'stock' if name in {'total_assets', 'total_equity', 'total_loans', 'loans_net_allowances', 'total_deposits'} or name.startswith('bank_sum_') else
                'YTD_flow' if name in {'net_income_ytd', 'bank_member_net_income_ytd'} else 'metadata'),
            'notes': f.get('reporting_note', core_fields.get(name, ('', 'See MVP_V1.md'))[1])})
    with duckdb.connect(str(out / 'mvp_v1.duckdb')) as con:
        con.execute('CREATE TABLE organisation_financials AS SELECT * FROM read_parquet(?) LIMIT 0', [str(source / 'organisation_financials.parquet')])
        write_csv(out / 'organisation_financials.csv', rows, cols)
        con.execute('INSERT INTO organisation_financials SELECT * FROM read_csv_auto(?,header=true,all_varchar=true)', [str(out / 'organisation_financials.csv')])
        export_table(con, 'organisation_financials', out)
        for table, data in [('financial_tests', checks), ('financial_tests_main', main_checks),
                            ('financial_quarantine', financial_quarantine), ('exceptions', exceptions), ('data_dictionary', dictionary_rows)]:
            if data:
                write_csv(out / (table + '.csv'), data, list(data[0]))
                con.execute(f'CREATE TABLE {table} AS SELECT * FROM read_csv_auto(?,header=true)', [str(out / (table + '.csv'))])
                con.execute(f'COPY {table} TO ? (FORMAT PARQUET)', [str(out / (table + '.parquet'))])
    for name in ('release_report.json', 'ownership_ledger.csv', 'measure_coverage.csv'):
        shutil.copyfile(source / name, out / ('upstream_' + name))
    shutil.copyfile(mapping_path, out / 'measure_mapping.json')
    result = {'version': 'MVP_V1', 'status': 'PACKAGED_RESEARCH_DRAFT' if accepted else 'FAILED_MVP_CHECKS',
              'mvp_scope_checks_pass': accepted, 'financially_certified': False,
              'approved_full_historical_release': False, 'periods': periods, 'rows': len(rows), 'columns': len(cols),
              'upstream_rows': len(raw_rows), 'additional_bank_only_groups_excluded': removed,
              'consolidated_bank_detail_withheld': deposits_suppressed,
              'uncertain_quarter_values_withheld': suppressed, 'unresolved_ownership_records': upstream['unresolved_ownership'],
              'duplicate_keys': duplicates, 'financial_tests_passed': passed,
              'financial_tests_failed': failures, 'financial_tests_not_testable': not_testable,
              'financial_tests_failed_input': sum(c['status'] == 'FAIL' for c in checks),
              'financial_rows_quarantined': len(financial_quarantine),
              'source_hash_checks': source_checks, 'upstream_manifest_sha256': sha256(source / 'release_report.json'),
              'mapping_sha256': sha256(mapping_path), 'created_at_utc': datetime.now(timezone.utc).isoformat(),
              'accepted_limitations': ['No pre-2023 history', 'Institution types/foreign ultimate parents not independently verified',
                  'Some detailed bank equivalents missing', 'No retrospective merger adjustment',
                  'Uncertain quarter flows withheld', 'No independent full-population filing certification',
                  'Missing components make some accounting tests not testable; absence of failures is not a full pass'],
              'source_build': str(source), 'output': str(out.resolve())}
    (out / 'mvp_manifest.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    report = ['# MVP v1 — research draft', '', f'Status: {result["status"]}',
              f'Coverage: 2023 Q1–2026 Q2; {len(rows):,} organisation-quarter rows; {len(cols)} columns.',
              f'Unique-key duplicates: {duplicates}. Source hash checks: {len(source_checks)} matched.',
              f'Financial tests: {passed:,} passed; {failures:,} failed; {not_testable:,} not testable due to missing inputs.',
              f'Input failures retained: {result["financial_tests_failed_input"]}; financial rows quarantined: {len(financial_quarantine)}. Main-table checks exclude these records, not their evidence.',
              f'Uncertain quarterly values withheld: {suppressed:,}.',
              f'Additional bank-only groups excluded: {removed}; consolidated groups with bank detail withheld: {deposits_suppressed}.',
              '', '## Agreed MVP assumptions', ''] + ['- ' + item for item in result['accepted_limitations']] + [
              '', 'The upstream release remains blocked for its original full-history/full-field target. This package closes the narrower MVP scope only.',
              'MVP delivery does not certify financial accuracy or approve research conclusions.',
              'Use exceptions.csv and upstream_measure_coverage.csv to inspect gaps. Empty values are not zero.',
              'The main table uses top-level RSSD keys, reported basis labels and ownership/perimeter flags.']
    (out / 'VALIDATION_REPORT.md').write_text('\n'.join(report) + '\n', encoding='utf-8')
    shutil.copyfile(root / 'MVP_V1.md', out / 'README.md')
    with zipfile.ZipFile(out / 'BPI_MVP_v1_RESEARCH_DRAFT.zip', 'x', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(out.iterdir()):
            if path.suffix != '.zip':
                bundle.write(path, path.name)
    print(json.dumps(result, indent=2))
    return 0 if accepted else 2


if __name__ == '__main__':
    raise SystemExit(main())
