"""Synthetic failure fixtures only; no synthetic financial rows enter real outputs."""
import json
from pathlib import Path
import re
import sys
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
import build_dataset as builder
from output_dictionary import build_dictionary
from public_processor import PublicJobs

ROOT=Path(__file__).parents[1]


def test_full_dictionary_matches_all_236_output_columns():
    columns=json.loads((ROOT/'config/public_columns.json').read_text())
    mapping=json.loads((ROOT/'config/expanded_measures.json').read_text())
    entries=build_dictionary(columns,mapping)
    assert len(entries)==236 and [e['column'] for e in entries]==columns
    assert all(e['notes'] and e['calculation'] and e['missingness'] for e in entries)
    by_name={e['column']:e for e in entries}
    assert by_name['top_rssd']['unit']=='metadata'
    assert by_name['total_assets']['measurement']=='stock'
    assert by_name['net_income_quarter']['measurement']=='quarterly_flow'
    assert by_name['bank_sum_DEP']['source_field']=='DEP'
    assert by_name['interest_loans_residential_ytd']['fdic_equivalent']==''
    assert 'VALIDATED_RESEARCH_DRAFT' in by_name['release_status']['notes']
    assert 'MVP_V1_RESEARCH_DRAFT' in by_name['release_status']['notes']


def test_period_plan_never_invents_missing_quarter_or_prior_flow():
    plan=builder.plan_period_delivery(['20240331','20240630'],{'20240630'},set())
    assert plan[0]['status']=='MISSING'
    assert plan[1]['status']=='DELIVERED_WITH_LIMITATIONS'
    assert 'PRIOR_QUARTER_UNAVAILABLE' in plan[1]['reason']


def configure_synthetic_sources(tmp_path,monkeypatch,blocked_structure=False):
    (tmp_path/'config').mkdir()
    (tmp_path/'config/expanded_measures.json').write_bytes((ROOT/'config/expanded_measures.json').read_bytes())
    def prepare(root,client,name,kind,q,*args):
        if q=='20240331' or (blocked_structure and kind=='CSV_RELATIONSHIPS.zip'):
            raise ValueError('Synthetic missing source fixture')
        return {'filename':name,'period':q,'snapshot':str(tmp_path/name),'sha256':'TEST_FIXTURE','acquisition':'TEST_FIXTURE'}
    def period(path):return re.search(r'\d{8}',Path(path).name)[0]
    monkeypatch.setattr(builder,'prepare_source',prepare)
    monkeypatch.setattr(builder,'zip_rows',lambda path:iter([]))
    monkeypatch.setattr(builder,'load_fdic_json',lambda path:[{'CERT':'1','REPDTE':period(path),'RSSDID':'20','RSSDHCR':'0','NAME':'Synthetic bank','ASSET':'100','EQ':'10','DEP':'70','NETINC':'2','NETINCQ':'1'}])
    monkeypatch.setattr(builder,'load_y9',lambda path,fields=None:[{'RSSD9001':'10','RSSD9999':period(path),'RSSD9017':'Synthetic holder','BHCK2170':'1000','BHCK4340':'10','BHCT3210':'100'}])


def test_partial_build_exports_good_quarter_and_explicit_missing_report(tmp_path,monkeypatch):
    configure_synthetic_sources(tmp_path,monkeypatch)
    assert builder.main(['--root',str(tmp_path),'--start','20240331','--end','20240630','--offline'])==2
    out=next((tmp_path/'outputs/dataset').iterdir())
    report=json.loads((out/'release_report.json').read_text())
    assert report['processing_status']=='PARTIAL'
    assert report['missing_periods']==['20240331'] and report['delivered_periods']==['20240630']
    import duckdb
    with duckdb.connect(str(out/'dataset.duckdb'),read_only=True) as con:
        assert con.execute('select distinct report_date from organisation_financials').fetchall()==[('20240630',)]
        assert con.execute('select count(*) from organisation_financials where net_income_quarter is not null').fetchone()[0]==0
    assert (out/'period_coverage.csv').exists()
    assert json.loads((out/'output_dictionary.json').read_text())['column_count']==236


def test_missing_structure_blocks_instead_of_guessing_ownership(tmp_path,monkeypatch):
    configure_synthetic_sources(tmp_path,monkeypatch,blocked_structure=True)
    assert builder.main(['--root',str(tmp_path),'--start','20240630','--end','20240630','--offline'])==1
    report=json.loads(next((tmp_path/'outputs/dataset').glob('*/release_report.json')).read_text())
    assert report['processing_status']=='BLOCKED_INPUTS' and report['missing_periods']==['20240630']


def test_public_worker_accepts_verified_partial_result(tmp_path,monkeypatch):
    jobs=PublicJobs(tmp_path)
    record={'id':'a'*32,'status':'QUEUED','start':'20240331','end':'20240630','result_ready':False,'events':[{'stage':'QUEUED','at':'test'}]}
    jobs.save(record)
    class Child:
        returncode=2
        def poll(self):return self.returncode
    def spawn(*args,**kwargs):
        command=args[0]
        out=Path(command[command.index('--output')+1]);out.mkdir(parents=True)
        other=tmp_path/'outputs/dataset/unrelated-cli';other.mkdir()
        (other/'release_report.json').write_text('{}')
        report={'requested_start':'20240331','requested_end':'20240630','processing_status':'PARTIAL','quality_policy':'CAUTIOUS_FLOW_AND_COMPONENT_CHECKS_V1',
                'source_errors':[{'filename':'missing'}],'period_coverage':[{'report_date':'20240331','status':'MISSING'}],
                'missing_periods':['20240331'],'delivered_periods':['20240630'],'requested_periods':['20240331','20240630'],
                'organisation_quarters':1,'failed_accounting_checks':0,'unresolved_ownership':0}
        (out/'release_report.json').write_text(json.dumps(report))
        return Child()
    monkeypatch.setattr('public_processor.subprocess.Popen',spawn)
    jobs.execute(record)
    result=jobs.get(record['id'])
    assert result['status']=='COMPLETED_PARTIAL_REVIEW_REQUIRED' and result['result_ready']
    assert result['missing_periods']==['20240331']
    assert PublicJobs(tmp_path).get(record['id'])['status']=='COMPLETED_PARTIAL_REVIEW_REQUIRED'


def test_explicit_output_rejects_paths_outside_dataset_directory(tmp_path):
    (tmp_path/'config').mkdir()
    (tmp_path/'config/expanded_measures.json').write_bytes((ROOT/'config/expanded_measures.json').read_bytes())
    with pytest.raises(SystemExit):
        builder.main(['--root',str(tmp_path),'--start','20240331','--end','20240331','--output',str(tmp_path/'wrong'),'--offline'])
    assert not (tmp_path/'wrong').exists()
