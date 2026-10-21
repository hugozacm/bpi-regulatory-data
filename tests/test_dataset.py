import sys
from pathlib import Path
import json
import pytest
sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
from build_dataset import quarters, needed_periods, bank_flow, safe_flow


def test_periods_are_contiguous_and_q1_needs_no_prior():
    assert quarters('20230930', '20240331') == ['20230930', '20231231', '20240331']
    assert needed_periods(['20240331']) == ['20240331']
    assert needed_periods(['20240630']) == ['20240331', '20240630']
    with pytest.raises(ValueError):
        quarters('20240401', '20241231')


def test_changed_membership_or_event_suppresses_bank_flow():
    members = [{'CERT': 1, 'NETINC': 9, 'NETINCQ': 4}]
    prior = {1: {'NETINC': 5}}
    assert bank_flow('20240630', members, prior, 'NETINC', True, False) == (4, 'AVAILABLE')
    assert bank_flow('20240630', members, prior, 'NETINC', False, False)[0] is None
    assert bank_flow('20240630', members, prior, 'NETINC', True, True)[0] is None
    members[0]['NETINCQ'] = 10
    assert bank_flow('20240630', members, prior, 'NETINC', True, False)[1] == 'FDIC_QUARTERLY_INCOME_DISAGREEMENT'


def test_missing_flow_and_year_reset():
    assert safe_flow('20240331', 10, None, True, False)[0] == 10
    assert safe_flow('20240630', 10, None, True, False)[0] is None


def test_mapping_is_unique_and_stock_is_not_differenced():
    mapping = json.loads((Path(__file__).parents[1] / 'config' / 'expanded_measures.json').read_text())
    fields = mapping['fields']
    assert len(fields) == 106
    assert len({field['name'] for field in fields}) == len(fields)
    equity = next(field for field in fields if field['name'] == 'holding_company_equity')
    assert equity['field'] == 'BHCT3210' and equity['type'] == 'stock'
    assert all(field['valid_from'] == '20230331' for field in fields)
