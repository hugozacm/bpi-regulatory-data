import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from build_legacy_quarter import holders_from_csv, mapped_flows


def test_parent_only_records_never_become_consolidated_finance(tmp_path):
    path=tmp_path/'holders.csv'
    path.write_text('RSSD9001,RSSD9999,BHCK2170,BHCP2170\n--------,--------,--------,--------\n1,20010331,100,200\n2,20010331,,300\n')
    identities, consolidated=holders_from_csv(path,'20010331')
    assert len(identities)==2
    assert [r['RSSD9001'] for r in consolidated]==['1']


def test_malformed_and_duplicate_holder_records_rejected(tmp_path):
    path=tmp_path/'holders.csv'
    path.write_text('RSSD9001,RSSD9999,BHCK2170\n1,20010331\n')
    with pytest.raises(ValueError): holders_from_csv(path,'20010331')
    path.write_text('RSSD9001,RSSD9999,BHCK2170\n1,20010331,100\n1,20010331,200\n')
    with pytest.raises(ValueError): holders_from_csv(path,'20010331')


def test_q1_ytd_not_divided_by_four_and_event_withholding():
    mapping={'ytd_fields':{'net_income':'BHCK4340'}}
    row={};mapped_flows(row,{'BHCK4340':'100'},mapping,False)
    assert row=={'net_income_ytd':100,'net_income_quarter':100}
    row={};mapped_flows(row,{'BHCK4340':'100'},mapping,True)
    assert row=={'net_income_ytd':100,'net_income_quarter':None}


def test_missing_financial_values_not_zero(tmp_path):
    path=tmp_path/'holders.csv'
    path.write_text('RSSD9001,RSSD9999,BHCK2170,BHCK4340\n1,20010331,100,.\n')
    _,holders=holders_from_csv(path,'20010331')
    row={};mapped_flows(row,holders[0],{'ytd_fields':{'net_income':'BHCK4340'}},False)
    assert row['net_income_ytd'] is None
