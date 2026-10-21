import io
import json
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))
import run_workflow as workflow


@pytest.fixture
def tmp_path(tmp_path_factory):
    # Keep hash-addressed fixture paths below legacy Windows MAX_PATH.
    from uuid import uuid4
    root = tmp_path_factory.getbasetemp() / uuid4().hex[:8]
    root.mkdir()
    return root


class Client:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return SimpleNamespace(content=self.content, text=self.content.decode('latin-1'), raise_for_status=lambda: None)


def fdic_bytes(period='20241231', total=1):
    row = dict.fromkeys(workflow.FDIC_FIELDS, None)
    row.update(CERT=1, REPDTE=period, NAME='Test fixture')
    return json.dumps({'meta': {'total': total}, 'data': [{'data': row}]}).encode()


def test_prior_quarter_and_bad_dates():
    assert workflow.previous_quarter('20240331') == '20231231'
    assert workflow.previous_quarter('20241231') == '20240930'
    with pytest.raises(ValueError):
        workflow.previous_quarter('20240229')


def test_download_snapshot_and_cached_rerun(tmp_path):
    client = Client(fdic_bytes())
    first = workflow.prepare_source(tmp_path, client, 'fdic_extended_20241231.json', 'fdic', '20241231')
    assert first['retrieved_at_utc']
    assert Path(first['snapshot']).read_bytes() == fdic_bytes()
    second = workflow.prepare_source(tmp_path, client, 'fdic_extended_20241231.json', 'fdic', '20241231', offline=True)
    assert len(client.calls) == 1
    assert second['sha256'] == first['sha256']
    assert second['retrieved_at_utc'] == first['retrieved_at_utc']


def test_local_import_does_not_invent_retrieval_time(tmp_path):
    research = tmp_path / 'research'
    research.mkdir()
    source = research / 'fdic_extended_20241231.json'
    source.write_bytes(fdic_bytes())
    record = workflow.prepare_source(tmp_path, Client(b''), source.name, 'fdic', '20241231', offline=True)
    assert record['retrieved_at_utc'] is None
    assert source.read_bytes() == fdic_bytes()


def test_refresh_preserves_existing_snapshot_and_legacy_file(tmp_path):
    research = tmp_path / 'research'
    research.mkdir()
    filename = 'fdic_extended_20241231.json'
    original = research / filename
    original.write_bytes(fdic_bytes())
    before = workflow.prepare_source(tmp_path, Client(b''), filename, 'fdic', '20241231', offline=True)
    changed = fdic_bytes().replace(b'Test fixture', b'Revised fixture')
    after = workflow.prepare_source(tmp_path, Client(changed), filename, 'fdic', '20241231', refresh=True)
    assert before['sha256'] != after['sha256']
    assert original.read_bytes() == fdic_bytes()
    assert Path(before['snapshot']).read_bytes() == fdic_bytes()
    reused = workflow.prepare_source(tmp_path, Client(b''), filename, 'fdic', '20241231', offline=True)
    assert reused['sha256'] == after['sha256']


@pytest.mark.parametrize('content', [b'<html>challenge</html>', fdic_bytes(total=2), fdic_bytes('20240930')])
def test_bad_fdic_is_not_cached(tmp_path, content):
    with pytest.raises((ValueError, KeyError)):
        workflow.prepare_source(tmp_path, Client(content), 'fdic_extended_20241231.json', 'fdic', '20241231')
    assert not list((tmp_path / 'research').rglob('*.part'))
    assert not (tmp_path / 'research' / 'snapshots').exists()


def test_nic_challenge_is_not_accepted_as_zip(tmp_path):
    with pytest.raises(ValueError, match='non-ZIP'):
        workflow.prepare_source(tmp_path, Client(b'<html>CAPTCHA</html>'), 'BHCF20241231.ZIP', 'y9', '20241231')


def test_structure_discovery_only_uses_official_literal_link():
    client = Client(b'<a href="/npw/FinancialReport/Example?zipfilename=CSV_RELATIONSHIPS.zip">zip</a>')
    assert workflow.discover_structure_url(client, 'CSV_RELATIONSHIPS.zip').startswith('https://www.ffiec.gov/')
    with pytest.raises(ValueError):
        workflow.discover_structure_url(Client(b'<a href="https://evil.example/CSV_RELATIONSHIPS.zip">bad</a>'), 'CSV_RELATIONSHIPS.zip')


def test_missing_offline_sources_produce_report_and_block_processing(tmp_path, monkeypatch):
    monkeypatch.setattr(workflow, 'run_quarter', lambda *a: pytest.fail('Must not process incomplete inputs'))
    assert workflow.main(['--root', str(tmp_path), '--period', '20240331', '--offline']) == 1
    report = json.loads(next((tmp_path / 'outputs').rglob('workflow_report.json')).read_text())
    assert report['processing_status'] == 'NOT_STARTED'
    assert len(report['sources']) == 4  # Q1 requires no preceding-year financials.
    assert all(row['status'] == 'BLOCKED' for row in report['sources'])


def test_completed_financial_failure_returns_two(tmp_path, monkeypatch):
    def ready(root, client, filename, kind, period, *args):
        return {'filename': filename, 'status': 'READY', 'snapshot': 'fixture'}
    monkeypatch.setattr(workflow, 'prepare_source', ready)
    monkeypatch.setattr(workflow, 'run_quarter', lambda *args: {'validation_pass': False})
    import history_audit
    monkeypatch.setattr(history_audit, 'main', lambda *args: None)
    assert workflow.main(['--root', str(tmp_path), '--period', '20240331', '--offline']) == 2
    assert next((tmp_path / 'outputs').rglob('workflow_report.md')).exists()


def test_invalid_structure_columns_are_rejected(tmp_path):
    path = tmp_path / 'bad.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('relationships.csv', 'wrong,columns\n1,2\n')
    with pytest.raises(ValueError, match='missing required'):
        workflow.validate_source(path, 'CSV_RELATIONSHIPS.zip')
