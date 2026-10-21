"""Conservative dated highest-parent grouping; no retroactive merger roll-up."""
import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from bpi_pipeline import (as_int, load_fdic_json, load_y9, quarter_from_ytd,
                          sha256, validate_period_pair, validate_records, write_csv, deposits_y9)
from history_audit import active_control_parents, zip_rows


def resolve_top(rssd, parents):
    if not rssd:
        return None, 'MISSING_RSSD'
    visiting, visited, roots = set(), set(), set()
    ambiguous = False

    def visit(node):
        nonlocal ambiguous
        if node in visiting:
            raise ValueError('CONTROL_CYCLE')
        if node in visited:
            return
        visiting.add(node)
        next_nodes = parents.get(node, set())
        ambiguous |= len(next_nodes) > 1
        if not next_nodes:
            roots.add(node)
        for parent in next_nodes:
            visit(parent)
        visiting.remove(node)
        visited.add(node)

    try:
        visit(rssd)
    except ValueError:
        return None, 'CONTROL_CYCLE'
    if ambiguous or len(roots) != 1:
        return None, 'AMBIGUOUS_CONTROL'
    top = next(iter(roots))
    return top, 'NO_PARENT_FOUND_CANDIDATE' if top == rssd else 'DATED_CONTROL_CHAIN'


def strict_sum(rows, field):
    values = [as_int(row.get(field)) for row in rows]
    return None if not values or any(value is None for value in values) else sum(values)


def build_groups(banks, holders, parents, period, prior_banks=(), prior_holders=()):
    prior_bank = {as_int(row['CERT']): row for row in prior_banks}
    prior_holder = {as_int(row['RSSD9001']): row for row in prior_holders}
    by_holder = {as_int(row['RSSD9001']): row for row in holders}
    groups, ledger = defaultdict(list), []
    for bank in banks:
        rssd, reported = as_int(bank.get('RSSDID')), as_int(bank.get('RSSDHCR'))
        top, status = resolve_top(rssd, parents)
        # Do not treat a missing NIC edge as independence if FDIC reports a holder.
        if top == rssd and reported not in (None, 0, rssd):
            top, status = None, 'FDIC_HOLDER_WITHOUT_NIC_PATH'
        elif top and reported not in (None, 0, rssd):
            from history_audit import ancestors
            if reported not in ancestors(rssd, parents):
                top, status = None, 'FDIC_NIC_DISAGREEMENT'
        ledger.append({'bank_cert': as_int(bank['CERT']), 'bank_rssd': rssd,
                       'reported_holder_rssd': reported, 'top_rssd': top,
                       'report_date': period, 'ownership_status': status})
        if top:
            groups[top].append(bank)
    # Keep holder-only groups visible, but never substitute an intermediate filing
    # for an ultimate parent's consolidated report.
    for rssd in by_holder:
        top, status = resolve_top(rssd, parents)
        if top:
            groups.setdefault(top, [])
        else:
            ledger.append({'bank_cert': None, 'bank_rssd': rssd, 'reported_holder_rssd': None,
                           'top_rssd': None, 'report_date': period, 'ownership_status': status})
    result = []
    for top, members in sorted(groups.items()):
        holder = by_holder.get(top)
        nested_banks = any(parent in {as_int(b.get('RSSDID')) for b in members}
                           for b in members for parent in parents.get(as_int(b.get('RSSDID')), ()))
        bank_only = holder is None
        row = {'entity_key': f'TOP_RSSD_{top}', 'top_rssd': top, 'report_date': period,
               'basis': 'CONSOLIDATED_Y9C' if holder else 'BANK_ONLY_AGGREGATE',
               'bank_count': len(members), 'release_status': 'REVIEW_REQUIRED',
               'coverage_note': 'Ultimate parent classification and bank membership require review',
               'nested_bank_overlap': nested_banks}
        row['bank_member_net_income_ytd'] = None if nested_banks else strict_sum(members, 'NETINC')
        for name, y9, fdic in [('total_assets', 'BHCK2170', 'ASSET'), ('total_equity', 'BHCK3210', 'EQ')]:
            row[name] = as_int(holder.get(y9)) if holder else (None if nested_banks else strict_sum(members, fdic))
        row['total_loans'] = as_int(holder.get('BHCK2122')) if holder else None
        row['loans_net_allowances'] = None if holder or nested_banks else strict_sum(members, 'LNLSNET')
        row['total_deposits'] = deposits_y9(holder) if holder else (None if nested_banks else strict_sum(members, 'DEP'))
        if holder:
            row['net_income_ytd'] = as_int(holder.get('BHCK4340'))
            row['net_income_quarter'] = quarter_from_ytd(period, row['net_income_ytd'], prior_holder.get(top, {}).get('BHCK4340'))
        else:
            # Current-member YTD is evidence, not an approved group flow across
            # mergers. Suppress until both membership and acquisition income
            # have been reconciled, rather than publish a misleading sum.
            row['net_income_ytd'] = None
            row['net_income_quarter'] = None
        for field in ('DEP', 'DEPDOM', 'DEPFOR', 'DEPIDOM', 'DEPNIDOM'):
            row['bank_sum_' + field] = None if nested_banks else strict_sum(members, field)
        if bank_only:
            row['coverage_note'] = 'Bank-only perimeter; nonbank activities/eliminations absent; membership-change flows need review'
        result.append(row)
    return result, ledger


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--period', default='20241231')
    a = p.parse_args(argv)
    from run_workflow import previous_quarter
    prior = previous_quarter(a.period)
    validate_period_pair(a.period, prior)
    research = a.root / 'research'
    inputs = {'banks': research / f'fdic_extended_{a.period}.json',
              'holders': research / f'BHCF{a.period}.ZIP',
              'relationships': research / 'CSV_RELATIONSHIPS.zip'}
    banks, holders = load_fdic_json(inputs['banks']), load_y9(inputs['holders'])
    validate_records(banks, 'CERT', 'REPDTE', a.period)
    validate_records(holders, 'RSSD9001', 'RSSD9999', a.period)
    old_banks, old_holders = [], []
    if a.period[4:6] != '03':
        inputs.update(prior_banks=research / f'fdic_extended_{prior}.json', prior_holders=research / f'BHCF{prior}.ZIP')
        old_banks, old_holders = load_fdic_json(inputs['prior_banks']), load_y9(inputs['prior_holders'])
        validate_records(old_banks, 'CERT', 'REPDTE', prior)
        validate_records(old_holders, 'RSSD9001', 'RSSD9999', prior)
    parents = active_control_parents(zip_rows(inputs['relationships']), a.period)
    rows, ledger = build_groups(banks, holders, parents, a.period, old_banks, old_holders)
    out = a.root / 'outputs' / 'top_level_pilot' / (a.period + '-' + uuid4().hex[:8])
    out.mkdir(parents=True)
    import duckdb
    with duckdb.connect(str(out / 'pilot.duckdb')) as con:
        for table, data in [('organisation_financials', rows), ('ownership_ledger', ledger)]:
            write_csv(out / (table + '.csv'), data, list(data[0]))
            con.execute(f'CREATE TABLE {table} AS SELECT * FROM read_csv_auto(?, header=true)', [str(out / (table + '.csv'))])
            con.execute(f'COPY {table} TO ? (FORMAT PARQUET)', [str(out / (table + '.parquet'))])
    summary = {'period': a.period, 'organisations': len(rows), 'basis_counts': dict(Counter(r['basis'] for r in rows)),
               'bank_records': len(banks),
               'ownership_ledger_status_counts': dict(Counter(r['ownership_status'] for r in ledger)),
               'nested_overlap_groups': sum(r['nested_bank_overlap'] for r in rows),
               'sources': {name: {'path': str(path.resolve()), 'sha256': sha256(path)} for name, path in inputs.items()},
               'processed_at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'REVIEW_REQUIRED',
               'limitations': 'Pilot core measures only; no expanded HI/HI-A/HI-B inventory; ambiguous banks excluded with ledger evidence; bank-only income not membership-adjusted; no historical rewrite'}
    (out / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    (out / 'REVIEW_REQUIRED.txt').write_text(summary['limitations'], encoding='utf-8')
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == '__main__':
    main()
