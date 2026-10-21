"""Build a provenance-preserving historical holding-company staging dataset.

Raw reported codes are preserved, not asserted to be comparable across years.
This is deliberately not the consolidated research-release table.
"""
import argparse
import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import duckdb

from bpi_pipeline import sha256
from history_sources import separator_row


def historical_rows(content, period):
    reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig')))
    reader.fieldnames = [s.strip().upper() for s in reader.fieldnames or []]
    if not {'RSSD9001', 'RSSD9999'} <= set(reader.fieldnames):
        raise ValueError('Historical identifiers/date missing')
    if len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ValueError('Duplicate historical columns')
    seen = set()
    for row in reader:
        if separator_row(row):
            continue
        if None in row or any(v is None for v in row.values()):
            raise ValueError('Ragged historical record')
        rssd = row['RSSD9001'].strip()
        date = row['RSSD9999'].strip().replace('-', '')
        if not rssd.isdigit() or int(rssd) <= 0 or date != period or rssd in seen:
            raise ValueError('Invalid/duplicate historical institution or wrong period')
        seen.add(rssd)
        for code, value in row.items():
            if code not in ('RSSD9001', 'RSSD9999') and value.strip() not in ('', '.', 'NA'):
                yield rssd, date, code, value.strip()
    if not seen:
        raise ValueError('Historical file contains no institution records')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--start', default='19860930')
    parser.add_argument('--end', default='20260630')
    args = parser.parse_args(argv)
    for date in (args.start, args.end):
        if len(date) != 8 or not date.isdigit() or date[4:] not in ('0331', '0630', '0930', '1231'):
            parser.error('Dates must be YYYYMMDD quarter ends')
    if args.start > args.end:
        parser.error('start is after end')
    root = args.root.resolve()
    manifest = root / 'research/history/chicago_manifest.json'
    inventory_bytes = manifest.read_bytes()
    inventory = json.loads(inventory_bytes)
    records = [r for r in inventory['archives'] if r['family'] == 'holding_company'
               and args.start <= r['period'] <= args.end and r.get('status') == 'DOWNLOADED']
    if not records:
        parser.error('No downloaded holding-company archives in requested range; run history_sources.py --download')
    out = root / 'outputs/history' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8])
    out.mkdir(parents=True)
    columns = ['rssd_id', 'report_date', 'reported_code', 'reported_value', 'source_url', 'source_sha256', 'mapping_status']
    sources, errors = [], []
    with (out / 'historical_reported_values.csv').open('w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for record in sorted(records, key=lambda r: r['period']):
            path = Path(record['snapshot'])
            try:
                if sha256(path) != record['sha256']:
                    raise ValueError('Snapshot hash mismatch')
                # Validate entire quarter before publishing any of its records.
                content = path.read_bytes()
                for _ in historical_rows(content, record['period']):
                    pass
                count = 0
                for row in historical_rows(content, record['period']):
                    writer.writerow((*row, record['source_url'], record['sha256'], 'RAW_CODE_NOT_HARMONISED'))
                    count += 1
                sources.append({'period': record['period'], 'sha256': record['sha256'], 'source_url': record['source_url'], 'values': count})
            except (ValueError, OSError) as error:
                errors.append({'period': record['period'], 'error': str(error)})
    with duckdb.connect(str(out / 'history.duckdb')) as con:
        con.execute('CREATE TABLE historical_reported_values AS SELECT * FROM read_csv(?, header=true, all_varchar=true)', [str(out / 'historical_reported_values.csv')])
        con.execute('COPY historical_reported_values TO ? (FORMAT PARQUET, COMPRESSION ZSTD)', [str(out / 'historical_reported_values.parquet')])
        count = con.execute('SELECT count(*) FROM historical_reported_values').fetchone()[0]
    available = {r['period'] for r in sources}
    requested = [f'{year}{q}' for year in range(int(args.start[:4]), int(args.end[:4])+1)
                 for q in ('0331','0630','0930','1231') if args.start <= f'{year}{q}' <= args.end]
    report = {'status': 'HISTORICAL_STAGING_NOT_RESEARCH_RELEASE', 'requested_start': args.start, 'requested_end': args.end,
              'reported_values': count, 'periods_loaded': sorted(available),
              'missing_requested_periods': [q for q in requested if q not in available],
              'requested_coverage_complete': set(requested) == available and not errors,
              'financially_certified': False, 'historical_harmonisation_complete': False,
              'sources': sources, 'errors': errors, 'inventory_sha256': hashlib.sha256(inventory_bytes).hexdigest(),
              'limitations': ['Raw reported strings, no historical code equivalence asserted',
                              'No stock/flow conversion or ownership aggregation applied',
                              'Bank SAS archives not yet parsed', 'Frozen MVP v1 unchanged']}
    (out / 'history_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'output': str(out), 'values': count, 'quarters': len(available), 'errors': errors}, indent=2))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
