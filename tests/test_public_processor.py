import io
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from public_processor import PublicAPI,PublicJobs,SITE


def request(api,path,method='GET',body=None,origin=None,query=''):
    raw=json.dumps(body).encode() if body is not None else b''
    env={'REQUEST_METHOD':method,'PATH_INFO':path,'QUERY_STRING':query,'CONTENT_TYPE':'application/json',
         'CONTENT_LENGTH':str(len(raw)),'wsgi.input':io.BytesIO(raw)}
    if origin:env['HTTP_ORIGIN']=origin
    result={}
    def respond(status,headers):result.update(status=status,headers=dict(headers))
    result['body']=b''.join(api(env,respond));return result


def root(tmp_path):
    (tmp_path/'config').mkdir()
    (tmp_path/'config/expanded_measures.json').write_text(json.dumps({'fields':[{'valid_from':'20230331','valid_to':'20260630'}]}))
    return tmp_path


def test_only_restricted_routes_public(tmp_path):
    api=PublicAPI(root(tmp_path))
    assert request(api,'/pilot/health')['status'].startswith('200')
    assert request(api,'/api/jobs','POST',{})['status'].startswith('404')
    assert request(api,'/research/CSV_RELATIONSHIPS.zip')['status'].startswith('404')
    assert request(api,'/pilot/health',origin='https://evil.example')['status'].startswith('403')
    assert request(api,'/pilot/jobs','POST',{},origin=SITE)['status'].startswith('422')
    assert request(api,'/pilot/jobs','POST',{})['status'].startswith('403')


def test_invalid_dates_never_start_process(tmp_path,monkeypatch):
    api=PublicAPI(root(tmp_path))
    monkeypatch.setattr('public_processor.subprocess.Popen',lambda *a,**k:pytest.fail('must not start'))
    for body in [{'start':'20010331','end':'20010331'},{'start':'20240331;echo x','end':'20240331'},
                 {'start':'20240331','end':'20240331','path':'/secret'}]:
        assert request(api,'/pilot/jobs','POST',body,origin=SITE)['status'].startswith('422')


def test_one_active_one_waiting_and_no_paths_in_status(tmp_path):
    jobs=PublicJobs(root(tmp_path));jobs.active='b'*32;jobs.last_started=0
    first=jobs.submit({'start':'20240331','end':'20240331'})
    assert first['status']=='QUEUED' and jobs.pending==first['id']
    with pytest.raises(RuntimeError):jobs.submit({'start':'20240331','end':'20240331'})
    first['result_directory']='private-folder';jobs.save(first)
    assert 'result_directory' not in jobs.get(first['id'])
    with pytest.raises(KeyError):jobs.get('../secret')


def test_restart_marks_job_interrupted(tmp_path):
    jobs=PublicJobs(root(tmp_path));job={'id':'a'*32,'status':'PROCESSING'};jobs.save(job)
    restarted=PublicJobs(tmp_path)
    assert restarted.get(job['id'])['status']=='INTERRUPTED'


def test_daily_limit_accepts_fiftieth_then_blocks_and_survives_restart(tmp_path,monkeypatch):
    from public_processor import utc
    jobs=PublicJobs(root(tmp_path))
    for index in range(49):
        jobs.save({'id':f'{index:032x}','status':'COMPLETED_REVIEW_REQUIRED','created_at_utc':utc()})
    monkeypatch.setattr('public_processor.threading.Thread.start',lambda self:None)
    accepted=jobs.submit({'start':'20240331','end':'20240331'})
    assert accepted['status']=='QUEUED'
    restarted=PublicJobs(tmp_path)
    with pytest.raises(RuntimeError,match='50 jobs'):
        restarted.submit({'start':'20240331','end':'20240331'})
    api=PublicAPI(tmp_path,jobs=restarted)
    assert json.loads(request(api,'/pilot/health')['body'])['daily_job_limit']==50


def test_daily_limit_excludes_previous_utc_day(tmp_path,monkeypatch):
    jobs=PublicJobs(root(tmp_path))
    for index in range(50):
        jobs.save({'id':f'{index:032x}','status':'COMPLETED_REVIEW_REQUIRED','created_at_utc':'2000-01-01T00:00:00+00:00'})
    monkeypatch.setattr('public_processor.threading.Thread.start',lambda self:None)
    assert jobs.submit({'start':'20240331','end':'20240331'})['status']=='QUEUED'


def test_results_unavailable_before_completion(tmp_path):
    jobs=PublicJobs(root(tmp_path));job={'id':'a'*32,'status':'BLOCKED','result_ready':False};jobs.save(job)
    api=PublicAPI(tmp_path,jobs=jobs)
    assert request(api,'/pilot/jobs/'+job['id']+'/result')['status'].startswith('422')
    assert request(api,'/pilot/jobs/'+job['id']+'/../../secret')['status'].startswith('404')


def test_chunk_download_matches_full_csv_and_rejects_invalid_parts(tmp_path):
    import hashlib
    jobs=PublicJobs(root(tmp_path));directory=tmp_path/'outputs/dataset/test-result';directory.mkdir(parents=True)
    (directory/'organisation_financials.csv').write_text('name,value\n=BAD,123\n'+('Example,456\n'*100000),encoding='utf-8')
    job={'id':'a'*32,'status':'COMPLETED_REVIEW_REQUIRED','result_ready':True,'result_directory':'test-result'};jobs.save(job)
    api=PublicAPI(tmp_path,jobs=jobs);base='/pilot/jobs/'+job['id']
    manifest=json.loads(request(api,base+'/result-manifest',origin=SITE)['body'])
    assert manifest['parts']>1
    parts=[request(api,base+'/result-part',origin=SITE,query='index='+str(i)) for i in range(manifest['parts'])]
    assert all(len(p['body'])<=1024*1024 for p in parts)
    joined=b''.join(p['body'] for p in parts)
    assert joined==request(api,base+'/result')['body']
    assert hashlib.sha256(joined).hexdigest()==manifest['sha256']
    assert joined.startswith(b'\xef\xbb\xbf') and b"'=BAD" in joined
    for query in ['index=-1','index=999','index=0&index=1','index=../../secret','path=x']:
        assert request(api,base+'/result-part',query=query)['status'].startswith('422')
    assert request(api,base+'/result-part',origin='https://evil.example',query='index=0')['status'].startswith('403')
    (directory/'validation.csv').write_text('status,value\nFAIL,1\n',encoding='utf-8')
    m=json.loads(request(api,base+'/result-manifest',query='file=validation')['body'])
    data=request(api,base+'/result-part',query='file=validation&index=0')['body']
    assert hashlib.sha256(data).hexdigest()==m['sha256']
    assert data==request(api,base+'/validation')['body']
    assert request(api,base+'/result-manifest',query='file=../../secret')['status'].startswith('422')
