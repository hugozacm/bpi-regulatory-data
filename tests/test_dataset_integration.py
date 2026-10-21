"""Optional official-source integration check; clean clones skip absent snapshots."""
import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
from bpi_pipeline import load_y9, quarter_from_ytd, as_int


def test_actual_expanded_y9_columns_and_equity_prefix():
    root = Path(__file__).parents[1]
    path = root / 'research' / 'BHCF20241231.ZIP'
    prior = root / 'research' / 'BHCF20240930.ZIP'
    if not path.exists() or not prior.exists():
        pytest.skip('Downloaded official fixtures are not included in the repository')
    mapping = json.loads((root / 'config' / 'expanded_measures.json').read_text())
    selected = ['RSSD9001', 'BHCK2170'] + [f['field'] for f in mapping['fields']]
    current = load_y9(path, fields=selected)
    old = {r['RSSD9001']: r for r in load_y9(prior, fields=selected)}
    assert any(as_int(r.get('BHCT3210')) is not None for r in current)
    checked = 0
    for row in current:
        income, expense, net = [as_int(row.get(f)) for f in ('BHCK4107', 'BHCK4073', 'BHCK4074')]
        if None not in (income, expense, net):
            assert income - expense == net
            checked += 1
        if row['RSSD9001'] in old:
            prev = old[row['RSSD9001']]
            actual = quarter_from_ytd('20241231', row.get('BHCK4107'), prev.get('BHCK4107'))
            if actual is not None:
                assert actual == income - as_int(prev['BHCK4107'])
    assert checked > 300
