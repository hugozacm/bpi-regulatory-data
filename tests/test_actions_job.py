import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
from run_actions_job import collect, main, quarter_end


@pytest.mark.parametrize('year,quarter', [('2024;echo x', '1'), ('2024', '5'), ('24', '1')])
def test_invalid_inputs(year, quarter):
    with pytest.raises(ValueError):
        quarter_end(year, quarter)


def test_quarter_end():
    assert quarter_end('2024', '2') == '20240630'


def test_validate_only(tmp_path, monkeypatch):
    (tmp_path / 'config').mkdir()
    (tmp_path / 'config/expanded_measures.json').write_text(json.dumps({'fields': [
        {'valid_from': '20230331', 'valid_to': '20260630'}]}))
    for key, value in {'FROM_YEAR': '2024', 'FROM_QUARTER': '1', 'TO_YEAR': '2024', 'TO_QUARTER': '1'}.items():
        monkeypatch.setenv(key, value)
    assert main(['--root', str(tmp_path), '--validate-only']) == 0
    monkeypatch.setenv('FROM_YEAR', '1986')
    assert main(['--root', str(tmp_path), '--validate-only']) == 1
    monkeypatch.setenv('FROM_YEAR', '2023')
    assert main(['--root', str(tmp_path), '--validate-only']) == 1  # five quarters


def test_collection_requires_completed_report(tmp_path):
    run = tmp_path / 'outputs/dataset/run'
    run.mkdir(parents=True)
    dest = tmp_path / 'artifact'
    dest.mkdir()
    (run / 'release_report.json').write_text(json.dumps({'processing_status': 'FAILED'}))
    with pytest.raises(ValueError, match='Processing blocked'):
        collect(tmp_path, set(), 2, dest)
    report = {'processing_status': 'COMPLETED', 'source_errors': []}
    (run / 'release_report.json').write_text(json.dumps(report))
    for name in ['organisation_financials.csv', 'organisation_financials.parquet',
                 'validation.csv', 'measure_coverage.csv', 'ownership_ledger.csv']:
        (run / name).write_text('fixture')
    assert collect(tmp_path, set(), 2, dest)['current_mvp_complete'] is False
    with pytest.raises(ValueError, match='cap'):
        collect(tmp_path, set(), 2, dest, limit=1)
    with pytest.raises(ValueError, match='exactly one'):
        collect(tmp_path, {run / 'release_report.json'}, 2, dest)
