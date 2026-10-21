import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from fed_scenarios import COLS, parse, points


def row(date, level, name='Actual'):
    return dict(zip(['Date','Scenario Name']+COLS,[date,name,'5',str(level),str(level),'6','3']))


def test_four_quarter_not_quarterly_returns():
    actual=[row('2025 Q1',100),row('2025 Q4',80)]
    severe=[row('2026 Q1',50,'Supervisory Severely Adverse')]
    p=points(actual,severe)[-1]
    assert p['stock_yoy']==-50
    assert p['cre_yoy']==-50
    assert p['bbb_spread']==3


def test_missing_lag_is_not_zero():
    assert points([row('2025 Q4',100)],[row('2026 Q1',50)])[1]['stock_yoy'] is None


def test_wrong_format_and_overlap_rejected():
    with pytest.raises(ValueError): parse(b'<html>blocked</html>','actual')
    with pytest.raises(ValueError): points([row('2026 Q1',100)],[row('2026 Q1',80)])
