import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
from release_mvp import freeze_flows, accounting_checks, EXPECTED_PERIODS, quarantine_conflicts


def test_mvp_suppresses_only_uncertain_quarter_flows():
    original = {'flow_perimeter_review': True, 'net_income_quarter': 7, 'net_income_ytd': 20, 'total_assets': 100}
    row, count = freeze_flows(original)
    assert row['net_income_quarter'] is None and count == 1
    assert row['net_income_ytd'] == 20 and row['total_assets'] == 100
    assert original['net_income_quarter'] == 7
    assert row['release_status'] == 'MVP_V1_RESEARCH_DRAFT'


def test_mvp_financial_checks_do_not_call_missing_values_pass():
    row = {'entity_key': 'TEST', 'report_date': '20240331',
           'interest_income_total_ytd': 10, 'interest_expense_total_ytd': 3, 'net_interest_income_ytd': 7}
    checks = accounting_checks(row)
    assert next(r for r in checks if r['check'] == 'NET_INTEREST_ytd')['status'] == 'PASS'
    assert next(r for r in checks if r['check'] == 'TRADING_REVENUE_COMPONENTS_ytd')['status'].startswith('NOT_TESTABLE')
    row['net_interest_income_ytd'] = 8
    assert next(r for r in accounting_checks(row) if r['check'] == 'NET_INTEREST_ytd')['status'] == 'FAIL'
    assert len(EXPECTED_PERIODS) == 14


def test_quarantine_keeps_original_conflicting_values_and_other_quarters():
    rows = [{'entity_key': 'TEST', 'report_date': '20240331', 'value': 5},
            {'entity_key': 'TEST', 'report_date': '20240630', 'value': 8}]
    checks = [{'entity_key': 'TEST', 'report_date': 20240331, 'status': 'FAIL'}]
    good, bad = quarantine_conflicts(rows, checks)
    assert good == [rows[1]] and bad == [rows[0]]
    assert bad[0]['value'] == 5 and len(rows) == 2
