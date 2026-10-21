import io
import json
import threading
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0,str(Path(__file__).parents[1]/'src'))

from backend_api import API, Jobs, validate_request


def call(app, path, method='GET', body=None, key=None, origin=None):
    raw=json.dumps(body).encode() if body is not None else b''
    env={'REQUEST_METHOD':method,'PATH_INFO':path,'QUERY_STRING':'','wsgi.input':io.BytesIO(raw),
         'CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(raw))}
    if key: env['HTTP_AUTHORIZATION']='Bearer '+key
    if origin: env['HTTP_ORIGIN']=origin
    response={}
    def start(status,headers): response.update(status=status,headers=dict(headers))
    response['body']=b''.join(app(env,start))
    return response


@pytest.fixture
def api_root(tmp_path):
    (tmp_path/'config').mkdir()
    (tmp_path/'config/expanded_measures.json').write_text(json.dumps({'fields':[{'valid_from':'20230331','valid_to':'20260630'}]}))
    return tmp_path


@pytest.mark.parametrize('body',[
    {'start':'20220331','end':'20230331'},
    {'start':'20241231','end':'20240331'},
    {'start':'20240330','end':'20241231'},
    {'start':'20230331','end':'20260630'},
    {'start':'20240331','end':'20241231','command':'whoami'},
    {'start':20240331,'end':'20241231'},
    [],
])
def test_rejects_unsupported_or_unbounded_jobs(api_root,body):
    with pytest.raises(ValueError):validate_request(body,api_root)


def test_job_ranges_validated_against_mapping(api_root):
    assert validate_request({'start':'20240331','end':'20241231'},api_root)==('20240331','20241231')


def test_jobs_disabled_without_operator_key(api_root):
    response=call(API(api_root,key=''),'/api/jobs','POST',{'start':'20240331','end':'20240331'})
    assert response['status'].startswith('503')


def test_operator_authentication_and_cors(api_root):
    app=API(api_root,key='k'*32,origins=['https://frontend.example'])
    assert call(app,'/api/jobs','POST',{},key='wrong')['status'].startswith('401')
    assert call(app,'/api/health',origin='https://evil.example')['status'].startswith('403')
    response=call(app,'/api/health',origin='https://frontend.example')
    assert response['headers']['Access-Control-Allow-Origin']=='https://frontend.example'
    assert 'Access-Control-Allow-Credentials' not in response['headers']
    assert call(app,'/api/jobs/../../config','GET',key='k'*32)['status'].startswith('404')


def test_public_health_does_not_expose_credentials_or_paths(api_root):
    response=call(API(api_root,key='secret'*8),'/api/health')
    assert response['status'].startswith('200')
    assert b'secret' not in response['body'] and str(api_root).encode() not in response['body']


def test_review_required_completion_and_fixed_subprocess_arguments(api_root):
    finished=threading.Event()
    def runner(args,**kwargs):
        assert args[1]==str(api_root/'src/build_dataset.py')
        assert '--start' in args and 'shell' not in kwargs
        directory=api_root/'outputs/dataset/test-result'
        directory.mkdir(parents=True)
        (directory/'release_report.json').write_text(json.dumps({'processing_status':'COMPLETED','source_errors':[],
            'organisation_quarters':1,'failed_accounting_checks':0}))
        (directory/'organisation_financials.csv').write_text('entity_key,total_assets\nTEST,123\n')
        return SimpleNamespace(returncode=2)
    jobs=Jobs(api_root,runner=runner)
    original=jobs.save
    def save(record):
        original(record)
        if record['status']=='COMPLETED_REVIEW_REQUIRED':finished.set()
    jobs.save=save
    record=jobs.submit({'start':'20240331','end':'20240331'})
    assert finished.wait(5)
    result=jobs.get(record['id'])
    assert result['status']=='COMPLETED_REVIEW_REQUIRED'
    assert result['historical_mvp_complete'] is False
    assert jobs.result_file(record['id']).is_file()
    with pytest.raises(RuntimeError):jobs.submit({'start':'20240331','end':'20240331'})


def test_restarted_jobs_not_claimed_running(api_root):
    jobs=Jobs(api_root)
    job_id='a'*32
    jobs.save({'id':job_id,'status':'RUNNING'})
    fresh=Jobs(api_root)
    assert fresh.get(job_id)['status']=='INTERRUPTED'
    with pytest.raises(KeyError):fresh.get('../credentials')


def test_invalid_request_never_spawns_job(api_root):
    app=API(api_root,key='k'*32)
    response=call(app,'/api/jobs','POST',{'start':'19860930','end':'19861231'},key='k'*32)
    assert response['status'].startswith('422')
    assert not (api_root/'outputs/api_jobs').exists()
