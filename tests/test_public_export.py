import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from build_public_demo import evidence_report


def test_export_evidence_does_not_require_a_fixed_run_id(tmp_path):
    path=tmp_path/'outputs/dataset/new-run/release_report.json';path.parent.mkdir(parents=True)
    value={'processing_status':'COMPLETED','quality_policy':'CAUTIOUS_FLOW_AND_COMPONENT_CHECKS_V1'}
    path.write_text(json.dumps(value))
    assert evidence_report(tmp_path)==value
    assert evidence_report(tmp_path,path)==value


def test_export_does_not_select_legacy_evidence_implicitly(tmp_path):
    path=tmp_path/'outputs/dataset/legacy/release_report.json';path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'processing_status':'COMPLETED'}))
    with pytest.raises(ValueError,match='evidence required'):evidence_report(tmp_path)
