"""Audit official NIC relationships/transformations without inventing merger weights."""
import argparse
import csv
import io
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from bpi_pipeline import sha256, write_csv

DICTIONARY = 'https://www.ffiec.gov/npw/StaticData/DataDownload/NPW%20Data%20Dictionary.pdf'


def zip_rows(path):
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if n.lower().endswith('.csv')]
        if len(names) != 1:
            raise ValueError('Expected exactly one CSV')
        with z.open(names[0]) as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8-sig', newline=''))
            reader.fieldnames = [n.lstrip('#').strip() for n in reader.fieldnames]
            yield from reader


def active_control_parents(rows, period):
    parents = defaultdict(set)
    for r in rows:
        if int(r['DT_START']) <= int(period) <= int(r['DT_END']) and r['CTRL_IND'] == '1' and r['RELN_LVL'] == '1':
            parents[int(r['ID_RSSD_OFFSPRING'])].add(int(r['ID_RSSD_PARENT']))
    return parents


def ancestors(rssd, parents):
    visited = set()
    todo = list(parents.get(rssd, ()))
    while todo:
        parent = todo.pop()
        if parent == rssd:
            raise ValueError('Ownership cycle')
        if parent in visited:
            continue
        visited.add(parent)
        todo.extend(parents.get(parent, ()))
    return visited


def classify_events(rows, start, end):
    selected = [r for r in rows if start <= r['DT_TRANS'] <= end]
    successors = defaultdict(set)
    for r in selected:
        successors[(r['ID_RSSD_PREDECESSOR'], r['DT_TRANS'])].add(r['ID_RSSD_SUCCESSOR'])
    result = []
    for r in selected:
        row = dict(r)
        code = r['TRNSFM_CD']
        multiple = len(successors[(r['ID_RSSD_PREDECESSOR'], r['DT_TRANS'])]) > 1
        row['review_status'] = ('MULTIPLE_SUCCESSORS_REVIEW' if multiple else
            'FAILURE_REVIEW' if code == '50' else
            'PARTIAL_OR_SPLIT_REVIEW' if code in ('5', '7', '9') else
            'CHARTER_DISCONTINUED_VERIFY_SCOPE' if code == '1' else 'UNKNOWN_EVENT_REVIEW')
        row['automatic_adjustment_approved'] = False
        row['definition_source'] = DICTIONARY
        result.append(row)
    return result


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--relationships', type=Path, required=True)
    p.add_argument('--transformations', type=Path, required=True)
    p.add_argument('--banks', type=Path, required=True)
    p.add_argument('--period', default='20241231')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(argv)
    a.output.mkdir(parents=True, exist_ok=True)
    parents = active_control_parents(zip_rows(a.relationships), a.period)
    banks = [r['data'] for r in json.loads(a.banks.read_text())['data']]
    ownership = []
    for b in banks:
        rssd = b.get('RSSDID')
        if not rssd:
            continue
        chain = ancestors(int(rssd), parents)
        holder = b.get('RSSDHCR')
        if holder and int(holder) != int(rssd):
            status = 'HOLDER_CONFIRMED_IN_NIC_CHAIN' if int(holder) in chain else 'FDIC_NIC_DISAGREEMENT_REVIEW'
        else:
            status = 'NO_CONTROL_PARENT_FOUND_IN_NIC' if not chain else 'MISSING_FDIC_HOLDER_WITH_NIC_PARENT_REVIEW'
        ownership.append({'report_date': a.period, 'bank_cert': b['CERT'], 'bank_rssd': rssd, 'bank_name': b['NAME'], 'fdic_holder': holder, 'nic_ancestors': '|'.join(map(str, sorted(chain))), 'status': status})
    events = classify_events(list(zip_rows(a.transformations)), '20230101', '20251231')
    write_csv(a.output/'ownership_audit.csv', ownership, ['report_date','bank_cert','bank_rssd','bank_name','fdic_holder','nic_ancestors','status'])
    columns = ['ID_RSSD_PREDECESSOR','ID_RSSD_SUCCESSOR','DT_TRANS','TRNSFM_CD','ACCT_METHOD','review_status','automatic_adjustment_approved','definition_source']
    write_csv(a.output/'merger_events_2023_2025.csv', events, columns)
    summary = {'bank_rows_audited':len(ownership),'ownership_status_counts':dict(Counter(r['status'] for r in ownership)), 'transformation_rows_2023_2025':len(events), 'event_status_counts':dict(Counter(r['review_status'] for r in events)), 'relationships_sha256':sha256(a.relationships),'transformations_sha256':sha256(a.transformations),'warning':'Current NIC publication contains dated history, not a vintage archive. Absence of an edge alone is not proof of independence. Transformation codes alone do not establish full asset transfer or accounting comparability.'}
    (a.output/'history_summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    main()
