"""Acquire official final 2026 domestic scenarios; keep immutable source receipts."""
import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import re
import requests

PAGE = 'https://www.federalreserve.gov/supervisionreg/dfa-stress-tests-2026.htm'
FILES = {'actual': '2026_Final_Historic_Domestic.csv',
         'severe': '2026_Final_Supervisory_Severely_Adverse_Domestic.csv'}
COLS = ['Unemployment rate', 'Commercial Real Estate Price Index (Level)',
        'Dow Jones Total Stock Market Index (Level)', 'BBB corporate yield', '10-year Treasury yield']


def parse(raw, scenario):
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''))
    if not set(['Scenario Name', 'Date'] + COLS) <= set(reader.fieldnames or []):
        raise ValueError('Missing Fed CSV columns')
    rows = list(reader)
    dates = [r['Date'] for r in rows]
    expected = 'Actual' if scenario == 'actual' else 'Supervisory Severely Adverse'
    if not rows or len(set(dates)) != len(dates) or any(
        not re.fullmatch(r'\d{4} Q[1-4]', r['Date']) or r['Scenario Name'] != expected for r in rows):
        raise ValueError('Unexpected scenario, date or duplicate quarter')
    for r in rows:
        for key in COLS:
            if r[key] and not Decimal(r[key]).is_finite():
                raise ValueError('Non-finite Fed value')
    return rows


def points(actual, severe):
    index = {r['Date']: r for r in actual}
    if max(index) >= min(r['Date'] for r in severe):
        raise ValueError('Historical/scenario periods overlap')
    index.update({r['Date']: r for r in severe})
    result = []
    for kind, rows in [('actual', actual), ('severe', severe)]:
        for r in rows:
            date = r['Date']
            prior = index.get(str(int(date[:4])-1) + date[4:], {})
            def yoy(col):
                if not r[col] or not prior.get(col) or Decimal(prior[col]) == 0:
                    return None
                return float((Decimal(r[col])/Decimal(prior[col])-1)*100)
            result.append({'quarter': date, 'series': kind,
                           'unemployment': float(r[COLS[0]]) if r[COLS[0]] else None,
                           'cre_yoy': yoy(COLS[1]), 'stock_yoy': yoy(COLS[2]),
                           'bbb_spread': float(Decimal(r[COLS[3]])-Decimal(r[COLS[4]]))
                           if r[COLS[3]] and r[COLS[4]] else None})
    return result


def main():
    root = Path(__file__).resolve().parents[1]
    out = root / 'research/fed_scenarios'
    out.mkdir(parents=True, exist_ok=True)
    receipts, datasets = [], {}
    for kind, filename in FILES.items():
        url = 'https://www.federalreserve.gov/supervisionreg/files/' + filename
        response = requests.get(url, timeout=(15,45))
        response.raise_for_status()
        datasets[kind] = parse(response.content, kind)
        digest = hashlib.sha256(response.content).hexdigest()
        path = out / digest / filename
        path.parent.mkdir(exist_ok=True)
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Modified source snapshot')
        if not path.exists():
            path.write_bytes(response.content)
        receipts.append({'series': kind, 'filename': filename, 'url': url, 'sha256': digest,
                         'retrieved_at_utc': datetime.now(timezone.utc).isoformat(), 'rows':len(datasets[kind])})
    data = {'exercise': 2026, 'source_page': PAGE, 'sources': receipts,
            'points': points(datasets['actual'], datasets['severe']),
            'definitions': {'unemployment':'Quarterly average unemployment rate, percent.',
                'cre_yoy':'100 × (CRE index / index four quarters earlier − 1), percent; calculated.',
                'stock_yoy':'100 × (stock index / index four quarters earlier − 1), percent; calculated price-index return, excludes dividends.',
                'bbb_spread':'BBB corporate yield minus 10-year Treasury yield, percentage points; calculated.'},
            'limitations':['2026 final vintage only; no 2020–2025 exercise overlay.',
                           'Hypothetical scenario, not a forecast or observed future outcome.',
                           'Macroeconomic context only; not a bank-loss model or merger adjustment.']}
    (out / 'fed-scenarios.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    print(json.dumps({'sources':receipts,'points':len(data['points'])},indent=2))


if __name__ == '__main__':
    main()
