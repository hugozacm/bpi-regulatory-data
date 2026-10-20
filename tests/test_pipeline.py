from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from bpi_pipeline import deposits_y9, quarter_from_ytd, validate_period_pair, validate_records, as_int, load_fdic_json
import pytest
import json


def test_q1_flow_is_ytd():
    assert quarter_from_ytd("20240331", "125", None) == 125


def test_non_q1_flow_is_difference():
    assert quarter_from_ytd("20241231", "1000", "700") == 300


def test_non_q1_missing_prior_is_not_invented():
    assert quarter_from_ytd("20241231", "1000", None) is None


def test_y9_deposits_sum_domestic_and_foreign_components():
    row = {"BHDM6631": "10", "BHDM6636": "20", "BHFN6631": "3", "BHFN6636": "4"}
    assert deposits_y9(row) == 37


def test_y9_blank_deposits_stay_null():
    assert deposits_y9({}) is None


def test_partial_deposits_not_silently_zeroed():
    assert deposits_y9({"BHDM6631": "10"}) is None


def test_nonadjacent_or_nonquarter_dates_rejected():
    with pytest.raises(ValueError):
        validate_period_pair("20241231", "20240630")
    with pytest.raises(ValueError):
        validate_period_pair("20241230", "20240930")
    validate_period_pair("20240331", "20231231")


def test_duplicate_and_wrong_period_rejected():
    rows = [{"id": 1, "date": "20241231"}]*2
    with pytest.raises(ValueError):
        validate_records(rows, "id", "date", "20241231")
    with pytest.raises(ValueError):
        validate_records(rows[:1], "id", "date", "20240930")


def test_integer_precision_and_fraction_rejection():
    assert as_int("9007199254740993") == 9007199254740993
    with pytest.raises(ValueError):
        as_int("1.5")


def test_truncated_api_response_rejected(tmp_path):
    path = tmp_path / "truncated.json"
    path.write_text(json.dumps({"meta": {"total": 2}, "data": [{"data": {"CERT": 1}}]}))
    with pytest.raises(ValueError):
        load_fdic_json(path)


def test_real_sample_outputs_reconcile(tmp_path):
    from bpi_pipeline import main
    import duckdb
    root = Path(__file__).parents[1]
    required = [root / "research" / n for n in ("BHCF20241231.ZIP", "BHCF20240930.ZIP", "fdic_extended_20241231.json", "fdic_20240930.json")]
    if not all(p.exists() for p in required):
        pytest.skip("Optional downloaded official fixtures not present")
    summary = main(["--y9-current", str(required[0]), "--y9-prior", str(required[1]), "--fdic-current", str(required[2]), "--fdic-prior", str(required[3]), "--output", str(tmp_path)])
    assert summary["validation_pass"]
    assert summary["release_status"] == "REVIEW_REQUIRED"
    with duckdb.connect(str(tmp_path / "bpi_mvp.duckdb"), read_only=True) as con:
        assert con.execute("select count(*) from financials_wide").fetchone()[0] == 8
        assert con.execute("select count(*) from ownership where included_as_separate_entity").fetchone()[0] == 0
        assert con.execute("select sum(bank_count) from deposits where entity_key like 'BHC_%'").fetchone()[0] == 13
        assert con.execute("select count(*) from read_parquet(?)", [str(tmp_path / "financials_wide.parquet")]).fetchone()[0] == 8


def test_nic_literal_quote_cannot_merge_records(tmp_path):
    import zipfile
    from bpi_pipeline import load_y9, Y9_FIELDS
    path=tmp_path/'literal_quote.zip'
    fields=Y9_FIELDS+['FREE_TEXT']
    row=['1','20241231']+['10']*(len(Y9_FIELDS)-2)+['unclosed " quote']
    row2=['2','20241231']+['20']*(len(Y9_FIELDS)-2)+['normal text']
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('data.txt','^'.join(fields)+'\n'+'^'.join(row)+'\n'+'^'.join(row2)+'\n')
    assert len(load_y9(path))==2
