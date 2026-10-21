import pytest
from build_historical import historical_rows


def test_preserves_raw_codes_values_and_missingness():
    rows = list(historical_rows(b'rssd9001,rssd9999,BHCK2170,BHCK4340\n123,19860930,100,.\n', '19860930'))
    assert rows == [('123', '19860930', 'BHCK2170', '100')]


@pytest.mark.parametrize('content', [
    b'RSSD9001,RSSD9999,X\n123,19861231,1\n',
    b'RSSD9001,RSSD9999,X\n123,19860930,1\n123,19860930,2\n',
    b'RSSD9001,RSSD9999,X\n,19860930,1\n',
    b'RSSD9001,RSSD9999,X\n123,19860930\n',
    b'RSSD9001,RSSD9999,X,X\n123,19860930,1,2\n',
    b'RSSD9001,RSSD9999,X\n',
])
def test_rejects_invalid_historical_records(content):
    with pytest.raises(ValueError):
        list(historical_rows(content, '19860930'))
