import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
from top_level import resolve_top, build_groups
from history_audit import active_control_parents


def test_top_chain_and_cycle_above_start():
    assert resolve_top(1, {1: {2}, 2: {3}}) == (3, 'DATED_CONTROL_CHAIN')
    assert resolve_top(1, {1: {2}, 2: {3}, 3: {2}})[1] == 'CONTROL_CYCLE'
    assert resolve_top(1, {1: {2, 3}})[1] == 'AMBIGUOUS_CONTROL'


def test_official_date_does_not_rewrite_earlier_ownership():
    edges = [{'DT_START': '20250401', 'DT_END': '99991231', 'CTRL_IND': '1', 'RELN_LVL': '1',
              'ID_RSSD_OFFSPRING': '1', 'ID_RSSD_PARENT': '2'}]
    assert resolve_top(1, active_control_parents(edges, '20250331'))[0] == 1
    assert resolve_top(1, active_control_parents(edges, '20250630'))[0] == 2


def bank(cert, rssd, holder, assets=10):
    return dict(CERT=cert, RSSDID=rssd, RSSDHCR=holder, ASSET=assets, EQ=2, DEP=5,
                LNLSNET=4, NETINC=1, DEPDOM=5, DEPFOR=None, DEPIDOM=3, DEPNIDOM=2)


def test_consolidated_core_not_added_to_subsidiary():
    holder = dict(RSSD9001=3, BHCK2170=100, BHCK3210=20, BHCK2122=40, BHCK4340=4)
    rows, _ = build_groups([bank(1, 1, 2)], [holder], {1: {2}, 2: {3}}, '20250331')
    assert len(rows) == 1 and rows[0]['total_assets'] == 100
    assert rows[0]['bank_sum_DEP'] == 5


def test_bank_only_and_unresolved_holder():
    rows, ledger = build_groups([bank(1, 1, 3), bank(2, 2, 3)], [], {1: {3}, 2: {3}}, '20250331')
    assert rows[0]['total_assets'] == 20
    assert rows[0]['basis'] == 'BANK_ONLY_AGGREGATE'
    assert rows[0]['bank_member_net_income_ytd'] == 2
    assert rows[0]['net_income_quarter'] is None
    rows, ledger = build_groups([bank(1, 1, 3)], [], {}, '20250331')
    assert rows == [] and ledger[0]['top_rssd'] is None


def test_nested_bank_core_is_not_double_counted():
    rows, _ = build_groups([bank(1, 1, 3), bank(2, 2, 3)], [], {1: {2}, 2: {3}}, '20250331')
    assert rows[0]['nested_bank_overlap'] and rows[0]['total_assets'] is None


def test_missing_bank_value_is_not_converted_to_zero():
    member = bank(1, 1, 3)
    member['ASSET'] = None
    rows, _ = build_groups([member, bank(2, 2, 3)], [], {1: {3}, 2: {3}}, '20250331')
    assert rows[0]['total_assets'] is None
