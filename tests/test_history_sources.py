import io
import zipfile

import pytest

from history_sources import check_archive, discover, inspect_content, period_from_label


def test_requested_range_filters_before_limit():
    from history_sources import select_records
    records=[{'period':p} for p in ('19860930','20010331','20010630','20210331')]
    assert select_records(records,'20010331','20010630',1)==[{'period':'20010331'}]
    assert select_records(records,'20240331','20240331')==[]


def test_official_dashed_separator_is_not_an_institution():
    raw=b'RSSD9001,RSSD9999,BHCK2170\n--------,--------,--------\n123,20010331,10\n'
    result=inspect_content(raw,'holding_company','20010331')
    assert result['records']==1 and result['separator_rows_skipped']==1
    from build_historical import historical_rows
    assert list(historical_rows(raw,'20010331'))==[('123','20010331','BHCK2170','10')]
    with pytest.raises(ValueError):
        inspect_content(raw.replace(b'123,20010331',b'123,--------'),'holding_company','20010331')


@pytest.mark.parametrize('label,family,expected', [
    ('call7603.zip', 'bank', '19760331'),
    ('call0012.zip', 'bank', '20001231'),
    ('call1012.zip', 'bank', '20101231'),
    ('BHCF86Q3', 'holding_company', '19860930'),
    ('BHCF00Q1.ZIP', 'holding_company', '20000331'),
    ('BHCF21Q1', 'holding_company', '20210331'),
    ('not a quarter', 'bank', None),
])
def test_labels(label, family, expected):
    assert period_from_label(label, family) == expected


def test_literal_official_links_only():
    html = '<a href="/archive.csv">BHCF86Q3</a><a href="https://example.com/x.csv">BHCF86Q4</a>'
    rows = discover(html, 'https://www.chicagofed.org/page', 'holding_company')
    assert len(rows) == 1
    assert rows[0]['source_url'] == 'https://www.chicagofed.org/archive.csv'


def test_csv_inspection_does_not_claim_harmonisation():
    data = b'rssd9001,rssd9999,BHCK2170\n123,19860930,10\n123,19860930,.\n'
    result = inspect_content(data, 'holding_company', '19860930')
    assert result['records'] == 2
    assert result['duplicate_rssd_ids'] == 1
    assert result['populated_y9c_assets'] == 1


@pytest.mark.parametrize('data', [
    b'rssd9001,rssd9999,BHCK2170\n123,19861231,10\n',
    b'rssd9001,rssd9999,BHCK2170\n123,19860930\n',
    b'<html>access denied</html>',
])
def test_invalid_csv_rejected(data):
    with pytest.raises(ValueError):
        inspect_content(data, 'holding_company', '19860930')


def test_zip_inventory_and_html_rejection():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('historic.xpt', b'sample')
    assert check_archive(buffer.getvalue())[0]['name'] == 'historic.xpt'
    with pytest.raises(ValueError):
        check_archive(b'<html>not data</html>')
