"""Discover/download literal official Chicago Fed archive links, without inventing history mappings."""
import argparse
import io
import csv
import json
import re
import zipfile
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bpi_pipeline import sha256
from run_workflow import session, check_access


PAGES = {
    'holding_company': ['https://www.chicagofed.org/banking/financial-institution-reports/bhc-data'],
    'bank': ['https://www.chicagofed.org/banking/financial-institution-reports/commercial-bank-data-complete-1976-2000',
             'https://www.chicagofed.org/banking/financial-institution-reports/commercial-bank-data-complete-2001-2010'],
}


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.href, self.label = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.href = dict(attrs).get('href')
            self.label = []

    def handle_data(self, data):
        if self.href:
            self.label.append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self.href:
            self.links.append((self.href, ''.join(self.label).strip()))
            self.href = None


def period_from_label(label, family):
    if family == 'holding_company':
        match = re.fullmatch(r'BHCF(\d{2})Q([1-4])(?:\.ZIP)?', label.strip(), re.I)
        if not match:
            return None
        yy, quarter = map(int, match.groups())
        year = (1900 if yy >= 86 else 2000) + yy
        return str(year) + ('0331', '0630', '0930', '1231')[quarter - 1]
    match = re.fullmatch(r'call(\d{2})(03|06|09|12)\.zip', label.strip(), re.I)
    if not match:
        return None
    yy, month = int(match[1]), match[2]
    year = (1900 if yy >= 76 else 2000) + yy
    return f'{year}{month}' + ('30' if month in ('06', '09') else '31')


def discover(html, page, family):
    parser = Links()
    parser.feed(html)
    result = []
    for href, label in parser.links:
        period = period_from_label(label, family)
        url = urljoin(page, href)
        parsed = urlparse(url)
        if period and parsed.hostname in ('www.chicagofed.org', 'chicagofed.org') and parsed.scheme == 'https' and parsed.path.lower().endswith(('.zip', '.csv', '.txt')):
            result.append({'family': family, 'period': period, 'label': label, 'source_url': url, 'discovery_page': page})
    return result


def check_archive(content):
    if not content.startswith(b'PK'):
        raise ValueError('Not a ZIP archive')
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        if archive.testzip() is not None or not archive.namelist():
            raise ValueError('Archive CRC/contents invalid')
        return [{'name': item.filename, 'uncompressed_bytes': item.file_size} for item in archive.infolist()]


def separator_row(row):
    """Chicago CSVs can include a full-width dashed separator, not an institution."""
    return bool(row) and None not in row and all(
        isinstance(v, str) and bool(v.strip()) and set(v.strip()) == {'-'} for v in row.values())


def inspect_content(content, family, period):
    if content.startswith(b'PK'):
        return {'format': 'ZIP', 'members': check_archive(content)}
    if family != 'holding_company':
        raise ValueError('Expected bank SAS XPORT ZIP')
    text = content.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(text))
    reader.fieldnames = [name.strip().upper() for name in (reader.fieldnames or [])]
    if not {'RSSD9001', 'RSSD9999', 'BHCK2170'} <= set(reader.fieldnames):
        raise ValueError('Historical CSV missing identifiers/date/assets fields')
    dates, ids, count, y9c, separators = set(), set(), 0, 0, 0
    for row in reader:
        if separator_row(row):
            separators += 1
            continue
        if None in row or any(value is None for value in row.values()):
            raise ValueError('Ragged historical CSV record')
        dates.add(row['RSSD9999'].strip().replace('-', ''))
        ids.add(row['RSSD9001'].strip())
        count += 1
        y9c += row.get('BHCK2170', '').strip() not in ('', '.', 'NA')
    if not count or dates != {period}:
        raise ValueError(f'Historical CSV date/row check failed: {sorted(dates)}')
    return {'format': 'CSV', 'records': count, 'separator_rows_skipped': separators, 'unique_rssd_ids': len(ids), 'populated_y9c_assets': y9c,
            'columns': reader.fieldnames, 'duplicate_rssd_ids': count - len(ids)}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--download', action='store_true')
    p.add_argument('--start', help='Inclusive YYYYMMDD quarter end; use with --end')
    p.add_argument('--end', help='Inclusive YYYYMMDD quarter end; use with --start')
    p.add_argument('--refresh', action='store_true', help='Fetch current official bytes; retain old hash snapshots for audit')
    p.add_argument('--family', choices=('all', 'bank', 'holding_company'), default='all')
    p.add_argument('--limit', type=int, help='Optional sample limit; omit to collect every discovered archive')
    a = p.parse_args(argv)
    if bool(a.start) != bool(a.end):
        p.error('Provide both --start and --end')
    if a.start:
        from build_dataset import quarters
        try:
            quarters(a.start, a.end)
        except (ValueError, TypeError) as error:
            p.error(str(error))
    if a.limit is not None and a.limit < 1:
        p.error('limit must be positive')
    out = a.root / 'research' / 'history'
    out.mkdir(parents=True, exist_ok=True)
    manifest = out / 'chicago_manifest.json'
    old = json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else {'archives': []}
    existing = {(r['family'], r['period']): r for r in old['archives']}
    records, errors = [], []
    with session() as client:
        for family, pages in PAGES.items():
            if a.family not in ('all', family):
                continue
            for page in pages:
                try:
                    response = client.get(page, timeout=(15, 45))
                    check_access(response)
                    discovered = discover(response.text, page, family)
                    if not discovered:
                        raise ValueError('No recognised archive links on official page; inspect page before continuing')
                    records.extend(discovered)
                except (requests.RequestException, ValueError) as error:
                    errors.append({'source_page': page, 'error': str(error)[:500]})
        records = sorted({(r['family'], r['period']): r for r in records}.values(), key=lambda r: (r['family'], r['period']))
        print('Discovered', len(records), 'official archive links', flush=True)
        selected = select_records(records, a.start, a.end, a.limit)
        for record in selected:
            key = record['family'], record['period']
            saved = existing.get(key)
            if not a.refresh and saved and saved.get('status') == 'DOWNLOADED' and Path(saved['snapshot']).is_file() and sha256(Path(saved['snapshot'])) == saved['sha256']:
                record.update(saved)
            elif not a.download:
                record['status'] = 'DISCOVERED_NOT_DOWNLOADED'
            else:
                try:
                    response = client.get(record['source_url'], timeout=(15, 45))
                    check_access(response)
                    inspection = inspect_content(response.content, record['family'], record['period'])
                    import hashlib
                    digest = hashlib.sha256(response.content).hexdigest()
                    suffix = '.zip' if inspection['format'] == 'ZIP' else '.csv'
                    target = out / 'snapshots' / digest / (record['family'] + '_' + record['period'] + suffix)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.exists():
                        if sha256(target) != digest:
                            raise ValueError('Existing snapshot modified')
                    else:
                        with target.open('xb') as handle:
                            handle.write(response.content)
                    record.update(status='DOWNLOADED', snapshot=str(target.resolve()), sha256=digest,
                                  bytes=len(response.content), inspection=inspection,
                                  retrieved_at_utc=datetime.now(timezone.utc).isoformat(),
                                  analytical_mapping_status='NOT_YET_VERIFIED')
                except (requests.RequestException, ValueError, zipfile.BadZipFile, OSError) as error:
                    record.update(status='DOWNLOAD_FAILED', error=str(error)[:500])
            existing[key] = record
            result = {'updated_at_utc': datetime.now(timezone.utc).isoformat(), 'archives': sorted(existing.values(), key=lambda r: (r['family'], r['period'])),
                      'discovery_errors': errors, 'note': 'Downloaded archives are not harmonised financial history. MVP v1 is unchanged.'}
            manifest.write_text(json.dumps(result, indent=2), encoding='utf-8')
            print(record['family'], record['period'], record['status'], flush=True)
        # Retain unselected discovered links even during a sample run.
        for record in records:
            existing.setdefault((record['family'], record['period']), dict(record, status='DISCOVERED_NOT_DOWNLOADED'))
    result = {'updated_at_utc': datetime.now(timezone.utc).isoformat(), 'archives': sorted(existing.values(), key=lambda r: (r['family'], r['period'])),
              'discovery_errors': errors, 'status_counts': dict(Counter(r.get('status') for r in existing.values())),
              'note': 'Archive-level ZIP checks only; formats, institution coverage, historical mappings and ownership still need validation. MVP v1 is unchanged.'}
    manifest.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'manifest': str(manifest), 'status_counts': result['status_counts'], 'discovery_errors': errors}, indent=2))
    return 1 if errors or any(r.get('status') == 'DOWNLOAD_FAILED' for r in selected) else 0


def select_records(records, start=None, end=None, limit=None):
    """Filter before sampling/downloading; never acquire unrequested periods."""
    selected = [r for r in records if not start or start <= r['period'] <= end]
    return selected[:limit] if limit else selected


if __name__ == '__main__':
    raise SystemExit(main())
