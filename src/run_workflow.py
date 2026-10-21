"""Snapshot official inputs and run a quarter without overwriting earlier outputs."""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse
from uuid import uuid4

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from bpi_pipeline import (
    FDIC_API, FDIC_FIELDS, Y9_URL, load_fdic_json, load_y9,
    main as run_quarter, sha256, validate_period_pair, validate_records,
)

NIC_FINANCIAL_PAGE = 'https://www.ffiec.gov/npw/FinancialReport/FinancialDataDownload'
NIC_STRUCTURE_PAGE = 'https://www.ffiec.gov/npw/FinancialReport/DataDownload/1000'
STRUCTURE_FIELDS = {
    'CSV_RELATIONSHIPS.zip': {'ID_RSSD_PARENT', 'ID_RSSD_OFFSPRING', 'DT_START', 'DT_END', 'RELN_LVL', 'CTRL_IND'},
    'CSV_TRANSFORMATIONS.zip': {'ID_RSSD_PREDECESSOR', 'ID_RSSD_SUCCESSOR', 'DT_TRANS', 'TRNSFM_CD', 'ACCT_METHOD'},
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def previous_quarter(period):
    date = datetime.strptime(period, '%Y%m%d')
    from calendar import monthrange
    year, month = (date.year - 1, 12) if date.month == 3 else (date.year, date.month - 3)
    prior = f'{year}{month:02d}{monthrange(year, month)[1]:02d}'
    validate_period_pair(period, prior)
    return prior


def fdic_params(period):
    return {'filters': f'REPDTE:{period}', 'fields': ','.join(FDIC_FIELDS),
            'limit': 10000, 'format': 'json', 'sort_by': 'ASSET', 'sort_order': 'DESC'}


def session():
    result = requests.Session()
    retry = Retry(total=2, backoff_factor=1, status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=('GET',), respect_retry_after_header=False)
    result.mount('https://', HTTPAdapter(max_retries=retry))
    return result


def discover_structure_url(client, filename):
    """Use only a literal published URL; never guess the structure download route."""
    response = client.get(NIC_STRUCTURE_PAGE, timeout=(15, 45))
    response.raise_for_status()
    html = unescape(response.text)
    for candidate in re.findall(r'''["']([^"'<>\s]+)["']''', html):
        if filename.lower() not in candidate.lower():
            continue
        url = urljoin(NIC_STRUCTURE_PAGE, candidate)
        parsed = urlparse(url)
        if parsed.scheme == 'https' and parsed.hostname == 'www.ffiec.gov' and (
            'zipfilename=' in url.lower() or parsed.path.lower().endswith('.zip')
        ):
            return url
    raise ValueError('No published direct ZIP link found; use the official NIC browser download')


def validate_source(path, kind, period=None):
    if kind == 'fdic':
        rows = load_fdic_json(path)
        validate_records(rows, 'CERT', 'REPDTE', period)
        missing = set(FDIC_FIELDS) - set.intersection(*(set(row) for row in rows))
        if missing:
            raise ValueError(f'FDIC fields absent: {sorted(missing)}')
    elif kind == 'y9':
        validate_records(load_y9(path), 'RSSD9001', 'RSSD9999', period)
    else:
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise ValueError('ZIP CRC validation failed')
            names = [name for name in archive.namelist() if name.lower().endswith('.csv')]
            if len(names) != 1:
                raise ValueError('Expected one structure CSV')
            with archive.open(names[0]) as raw:
                reader = csv.DictReader(io.TextIOWrapper(raw, encoding='utf-8-sig', newline=''))
                fields = {name.lstrip('#').strip() for name in (reader.fieldnames or [])}
                if not STRUCTURE_FIELDS[kind] <= fields or next(reader, None) is None:
                    raise ValueError('Structure CSV missing required columns or records')


def prepare_source(root, client, filename, kind, period=None, offline=False, refresh=False):
    """Never modify legacy research files. Immutable hash-addressed copies are inputs."""
    research = root / 'research'
    source = research / filename
    record = {'filename': filename, 'kind': kind, 'period': period, 'observed_at_utc': utc_now(),
              'retrieved_at_utc': None, 'source_url': None, 'request_parameters': None}
    if kind == 'fdic':
        record.update(source_url=FDIC_API, request_parameters=fdic_params(period))
    elif kind == 'y9':
        record['source_url'] = Y9_URL.format(period=period)
    else:
        record['source_page'] = NIC_STRUCTURE_PAGE
    # Prior automated downloads are discoverable without replacing browser snapshots.
    receipt = research / 'download_cache' / (filename + '.json')
    if receipt.exists() and not refresh:
        cached = json.loads(receipt.read_text(encoding='utf-8'))
        source = research / 'snapshots' / cached['sha256'] / filename
        if sha256(source) != cached['sha256']:
            raise ValueError(f'Cached snapshot hash mismatch: {filename}')
        record.update(source_url=cached.get('source_url'), retrieved_at_utc=cached.get('retrieved_at_utc'))
    if source.exists() and not refresh:
        validate_source(source, kind, period)
        record['acquisition'] = 'REUSED_LOCAL'
        data_path = source
    else:
        if offline:
            raise ValueError(f'Missing source in offline mode: {filename}')
        if kind in STRUCTURE_FIELDS:
            record['source_url'] = discover_structure_url(client, filename)
        response = client.get(record['source_url'], params=record['request_parameters'], timeout=(15, 45))
        response.raise_for_status()
        if kind != 'fdic' and not response.content.startswith(b'PK'):
            raise ValueError('Expected ZIP, received non-ZIP (possibly a browser challenge)')
        staging = research / 'download_cache'
        staging.mkdir(parents=True, exist_ok=True)
        data_path = staging / (uuid4().hex + '.part')
        try:
            with data_path.open('xb') as handle:
                handle.write(response.content)
            validate_source(data_path, kind, period)
        except Exception:
            data_path.unlink(missing_ok=True)
            raise
        record.update(acquisition='DOWNLOADED', retrieved_at_utc=utc_now())
    digest = sha256(data_path)
    snapshot = research / 'snapshots' / digest / filename
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    if snapshot.exists():
        if sha256(snapshot) != digest:
            raise ValueError(f'Existing snapshot was modified: {snapshot}')
    else:
        with snapshot.open('xb') as target, data_path.open('rb') as origin:
            shutil.copyfileobj(origin, target)
    record.update(sha256=digest, snapshot=str(snapshot.resolve()), status='READY')
    if record['acquisition'] == 'DOWNLOADED':
        data_path.unlink()
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps(record, indent=2), encoding='utf-8')
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--period', default='20241231', help='One calendar quarter end, YYYYMMDD')
    parser.add_argument('--offline', action='store_true', help='Only use validated saved sources')
    parser.add_argument('--refresh', action='store_true', help='Fetch new snapshots; preserve existing files')
    parser.add_argument('--download-only', action='store_true')
    args = parser.parse_args(argv)
    if args.offline and args.refresh:
        parser.error('--offline and --refresh are mutually exclusive')
    prior = previous_quarter(args.period)
    root = args.root.resolve()
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8]
    output = root / 'outputs' / 'automated' / run_id
    output.mkdir(parents=True, exist_ok=False)
    report = {'run_id': run_id, 'period': args.period, 'started_at_utc': utc_now(),
              'release_status': 'REVIEW_REQUIRED', 'sources': [], 'processing_status': 'NOT_STARTED',
              'scope': 'Quarterly intermediate outputs; not the NIC-filtered organisation panel or merger-adjusted history'}
    specs = []
    for period in ([args.period] if args.period[4:6] == '03' else [args.period, prior]):
        specs.extend([(f'BHCF{period}.ZIP', 'y9', period), (f'fdic_extended_{period}.json', 'fdic', period)])
    specs.extend((name, name, None) for name in STRUCTURE_FIELDS)
    with session() as client:
        for filename, kind, period in specs:
            try:
                record = prepare_source(root, client, filename, kind, period, args.offline, args.refresh)
            except (requests.RequestException, ValueError, OSError, KeyError, zipfile.BadZipFile) as error:
                record = {'filename': filename, 'status': 'BLOCKED', 'error': str(error)[:500],
                          'manual_step': f'Download {filename} from the official source into {root / "research"}, then rerun without --refresh.',
                          'source_page': NIC_FINANCIAL_PAGE if kind == 'y9' else NIC_STRUCTURE_PAGE if kind in STRUCTURE_FIELDS else FDIC_API}
            report['sources'].append(record)
            print(filename, record['status'], flush=True)
    blocked = any(row['status'] != 'READY' for row in report['sources'])
    code = 1 if blocked else 0
    if not blocked and not args.download_only:
        sources = {row['filename']: row['snapshot'] for row in report['sources']}
        try:
            summary = run_quarter(['--period', args.period, '--prior-period', prior, '--all-bhcs', '--all-bank-candidates',
                '--y9-current', sources[f'BHCF{args.period}.ZIP'], '--y9-prior', sources.get(f'BHCF{prior}.ZIP', sources[f'BHCF{args.period}.ZIP']),
                '--fdic-current', sources[f'fdic_extended_{args.period}.json'], '--fdic-prior', sources.get(f'fdic_extended_{prior}.json', sources[f'fdic_extended_{args.period}.json']),
                '--output', str(output / args.period)])
            import history_audit
            history_audit.main(['--relationships', sources['CSV_RELATIONSHIPS.zip'], '--transformations', sources['CSV_TRANSFORMATIONS.zip'],
                '--banks', sources[f'fdic_extended_{args.period}.json'], '--period', args.period, '--output', str(output / 'ownership_review')])
            report.update(processing_status='COMPLETED', financial_summary=summary)
            code = 0 if summary['validation_pass'] else 2
        except Exception as error:
            report.update(processing_status='FAILED', processing_error=str(error))
            code = 1
    report.update(finished_at_utc=utc_now(), exit_code=code)
    (output / 'workflow_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    lines = ['# Workflow review report', '', f'Quarter: {args.period}',
             f'Processing: {report["processing_status"]}; exit code: {code}',
             'Release: REVIEW_REQUIRED', '',
             'This run does not produce the final NIC-filtered organisation panel or merger-adjusted history.', '', '## Sources', '']
    for row in report['sources']:
        lines.append(f'- {row["filename"]}: {row["status"]}')
        if row['status'] != 'READY':
            lines.extend([f'  - {row["error"]}', f'  - {row["manual_step"]}'])
    if 'financial_summary' in report:
        lines.extend(['', f'Financial checks passed: {report["financial_summary"]["validation_pass"]}',
                      'Inspect the quarter folder validation.csv and ownership_review/history_summary.json.'])
    if 'processing_error' in report:
        lines.extend(['', f'Processing error: {report["processing_error"]}'])
    (output / 'workflow_report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (output / 'REVIEW_REQUIRED.txt').write_text('Diagnostic draft only. Inspect workflow_report.json and quarterly validation.csv.\nNo merger-adjusted history or publication approval.\n', encoding='utf-8')
    print(f'Report: {output / "workflow_report.json"}', flush=True)
    return code


if __name__ == '__main__':
    sys.exit(main())
