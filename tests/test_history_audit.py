from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from history_audit import active_control_parents, ancestors, classify_events


def test_control_dates_and_indirect_paths():
    rows=[{'DT_START':'20230101','DT_END':'20231231','CTRL_IND':'1','RELN_LVL':'1','ID_RSSD_OFFSPRING':'1','ID_RSSD_PARENT':'2'},
          {'DT_START':'20230101','DT_END':'99991231','CTRL_IND':'1','RELN_LVL':'1','ID_RSSD_OFFSPRING':'2','ID_RSSD_PARENT':'3'}]
    parents=active_control_parents(rows,'20231231')
    assert ancestors(1,parents)=={2,3}
    assert ancestors(1,active_control_parents(rows,'20240331'))==set()


def test_noncontrol_is_not_ownership():
    rows=[{'DT_START':'20230101','DT_END':'99991231','CTRL_IND':'2','RELN_LVL':'1','ID_RSSD_OFFSPRING':'1','ID_RSSD_PARENT':'2'}]
    assert ancestors(1,active_control_parents(rows,'20241231'))==set()


def test_multisuccessor_and_failure_never_auto_adjust():
    rows=[{'ID_RSSD_PREDECESSOR':'1','ID_RSSD_SUCCESSOR':s,'DT_TRANS':'20230401','TRNSFM_CD':'1','ACCT_METHOD':'2'} for s in ('2','3')]
    result=classify_events(rows,'20230101','20251231')
    assert all(r['review_status']=='MULTIPLE_SUCCESSORS_REVIEW' and not r['automatic_adjustment_approved'] for r in result)
