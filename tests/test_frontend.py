import json
import threading
from functools import partial
from http.server import ThreadingHTTPServer
from urllib.request import urlopen, Request
from urllib.error import HTTPError

import duckdb
import pytest

from serve_frontend import Handler, dataset, safe_csv


def test_csv_formula_protection_and_integer_precision():
    assert safe_csv('=SUM(A1)') == "'=SUM(A1)"
    assert safe_csv(' @cmd') == "' @cmd"
    assert safe_csv('-1234567890123456789') == '-1234567890123456789'
    assert safe_csv(None) == ''


def test_empty_local_dataset(tmp_path):
    assert dataset(tmp_path, {})['rows'] == []


def test_real_database_filtering_preserves_precision(tmp_path):
    folder = tmp_path / 'outputs/mvp_v1/20261021T000000Z-test'
    folder.mkdir(parents=True)
    with duckdb.connect(str(folder / 'mvp_v1.duckdb')) as con:
        con.execute('CREATE TABLE organisation_financials(entity_key VARCHAR,name VARCHAR,top_rssd BIGINT,report_date VARCHAR,basis VARCHAR,total_assets BIGINT)')
        con.execute("INSERT INTO organisation_financials VALUES ('TOP_1','Test Bank',1,'19860930','BANK_ONLY_AGGREGATE',9007199254740993)")
    data = dataset(tmp_path, {'report_date': ['19860930'], 'search': ['test']})
    assert data['rows'][0]['total_assets'] == '9007199254740993'
    assert data['dates'] == ['19860930']
    assert dataset(tmp_path, {'search': ["' OR 1=1 --"]})['total'] == 0
    assert dataset(tmp_path, {'report_date': ['20230331']})['total'] == 0
    assert dataset(tmp_path, {'start': ['19860331'], 'end': ['19860930']})['total'] == 1
    assert dataset(tmp_path, {'start': ['19861231'], 'end': ['19861231']})['total'] == 0
    with pytest.raises(ValueError, match='From quarter'):
        dataset(tmp_path, {'start': ['19861231'], 'end': ['19860930']})
    with pytest.raises(ValueError, match='quarter ends'):
        dataset(tmp_path, {'start': ['19860830']})


def test_http_does_not_serve_arbitrary_files(tmp_path):
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, root=tmp_path))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = 'http://127.0.0.1:' + str(server.server_port)
    try:
        assert json.load(urlopen(base + '/api/dataset'))['total'] == 0
        with pytest.raises(HTTPError) as error:
            urlopen(base + '/config/delivery_scope.json')
        assert error.value.code == 404
        with pytest.raises(HTTPError) as error:
            urlopen(Request(base + '/api/dataset', headers={'Host': 'untrusted.example'}))
        assert error.value.code == 403
    finally:
        server.shutdown()
        server.server_close()
