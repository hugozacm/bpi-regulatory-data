import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from request_dataset import main, completed_modern


def fixture(root):
    (root/'config').mkdir()
    mapping=root/'config/expanded_measures.json'
    mapping.write_text(json.dumps({'fields':[{'valid_from':'20230331','valid_to':'20260630'}]}))
    out=root/'outputs/dataset/test'
    out.mkdir(parents=True)
    (out/'organisation_financials.csv').write_text('entity_key,report_date,name\nTOP_1,20230331,=unsafe\n')
    report={'requested_start':'20230331','requested_end':'20230331','processing_status':'COMPLETED',
            'source_errors':[],'sources':[],'mapping_sha256':hashlib.sha256(mapping.read_bytes()).hexdigest(),
            'organisation_quarters':1,'failed_accounting_checks':0,'unresolved_ownership':0}
    (out/'release_report.json').write_text(json.dumps(report))
    return out


def test_partial_run_continues_and_exports_only_completed_quarters(tmp_path):
    fixture(tmp_path)
    assert main(['--root',str(tmp_path),'--start','20221231','--end','20230331','--offline'])==2
    out=tmp_path/'outputs/requests/20221231-20230331'
    report=json.loads((out/'status.json').read_text())
    assert report['status']=='PARTIAL_REVIEW_REQUIRED'
    assert [r['output_ready'] for r in report['periods']]==[False,True]
    assert report['periods'][1]['reused_completed_build']
    assert "'=unsafe" in (out/'organisation_financials.csv').read_text()


def test_mapping_change_invalidates_reusable_build(tmp_path):
    fixture(tmp_path)
    assert completed_modern(tmp_path,'20230331')
    mapping=tmp_path/'config/expanded_measures.json'
    mapping.write_text(mapping.read_text()+'\n')
    assert completed_modern(tmp_path,'20230331') is None


def test_missing_source_invalidates_reusable_build(tmp_path):
    out=fixture(tmp_path)
    path=out/'release_report.json'
    report=json.loads(path.read_text());report['sources']=[{'snapshot':str(tmp_path/'missing'),'sha256':'none'}]
    path.write_text(json.dumps(report))
    assert completed_modern(tmp_path,'20230331') is None
