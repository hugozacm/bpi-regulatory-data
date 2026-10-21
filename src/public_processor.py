"""Restricted, opt-in public pilot API. No generic filesystem, shell or operator API routes."""
import csv
import hashlib
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs
from uuid import uuid4

from backend_api import validate_request
from serve_frontend import ROOT, dataset, safe_csv
from output_dictionary import build_dictionary

SITE='https://bpi-regulatory-research-hugo.amusedvine18.chatgpt.site'
TERMINAL={'COMPLETED_REVIEW_REQUIRED','COMPLETED_PARTIAL_REVIEW_REQUIRED','BLOCKED','FAILED','TIMED_OUT','INTERRUPTED'}


def utc(): return datetime.now(timezone.utc).isoformat()


class PublicJobs:
    def __init__(self, root=ROOT):
        self.root=Path(root);self.folder=self.root/'outputs/public_jobs'
        self.folder.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.active=None;self.pending=None;self.last_started=0
        # Interrupted work is never falsely displayed as still running.
        for file in self.folder.glob('*.json'):
            if len(file.stem)!=32: continue
            record=json.loads(file.read_text(encoding='utf-8'))
            if record.get('status') not in TERMINAL:
                record.update(status='INTERRUPTED',message='Local processor restarted; cached sources remain available')
                self.save(record)

    def save(self, record):
        with self.lock:
            record['updated_at_utc']=utc()
            path=self.folder/(record['id']+'.json');temporary=path.with_suffix('.tmp')
            temporary.write_text(json.dumps(record,indent=2),encoding='utf-8');temporary.replace(path)

    def get(self, job_id, public=True):
        if not re.fullmatch(r'[0-9a-f]{32}',job_id): raise KeyError(job_id)
        with self.lock:
            file=self.folder/(job_id+'.json')
            if not file.is_file(): raise KeyError(job_id)
            record=json.loads(file.read_text(encoding='utf-8'))
        if public: record.pop('result_directory',None)
        return record

    def submit(self, body):
        start,end=validate_request(body,self.root,max_quarters=14)
        with self.lock:
            if self.pending: raise RuntimeError('One job is running and one is queued. Please try later.')
            if time.monotonic()-self.last_started<60: raise RuntimeError('Please wait 60 seconds between submissions.')
            today=utc()[:10]
            daily=sum(json.loads(p.read_text(encoding='utf-8')).get('created_at_utc','').startswith(today) for p in self.folder.glob('*.json') if len(p.stem)==32)
            if daily>=10: raise RuntimeError('Daily pilot limit reached (10 jobs). Try again tomorrow.')
            if shutil.disk_usage(self.root).free<2*1024**3: raise RuntimeError('Processor disk space is low; operator action required.')
            record={'id':uuid4().hex,'start':start,'end':end,'status':'QUEUED','message':'Waiting for the single local processing slot',
                    'created_at_utc':utc(),'result_ready':False,'financially_certified':False,'events':[{'stage':'QUEUED','at':utc()}]}
            self.save(record);self.last_started=time.monotonic()
            if self.active: self.pending=record['id']
            else:
                self.active=record['id'];threading.Thread(target=self.execute,args=(record,),daemon=True).start()
            return self.get(record['id'])

    def execute(self, record):
        child=None
        try:
            record.update(status='CHECKING_SOURCES',message='Checking saved files and acquiring missing sources');self.save(record)
            before=set((self.root/'outputs/dataset').glob('*/release_report.json'))
            progress=self.folder/(record['id']+'.progress.json')
            with (self.folder/(record['id']+'.log')).open('w',encoding='utf-8') as log:
                child=subprocess.Popen([sys.executable,str(self.root/'src/build_dataset.py'),'--root',str(self.root),
                                        '--start',record['start'],'--end',record['end'],'--progress-file',str(progress)],
                                       cwd=self.root,stdout=log,stderr=subprocess.STDOUT)
                deadline=time.monotonic()+1800
                while child.poll() is None:
                    if time.monotonic()>deadline:
                        child.kill();child.wait();raise TimeoutError()
                    if progress.is_file():
                        receipt=json.loads(progress.read_text(encoding='utf-8'))
                        for event in receipt.get('events',[]):
                            if event not in record['events']:record['events'].append(event)
                        # Final success is assigned only after checking the actual output report.
                        if receipt['stage']!='COMPLETED_REVIEW_REQUIRED':
                            record.update(status=receipt['stage'],message=receipt['message']);self.save(record)
                    time.sleep(.5)
            reports=set((self.root/'outputs/dataset').glob('*/release_report.json'))-before
            if len(reports)!=1: raise ValueError('Expected one build report')
            report_path=reports.pop();report=json.loads(report_path.read_text(encoding='utf-8'))
            for key in ('requested_periods','delivered_periods','missing_periods','period_coverage'):
                record[key]=report.get(key,[])
            partial=report.get('processing_status')=='PARTIAL' and bool(report.get('period_coverage')) and bool(report.get('quality_policy'))
            if child.returncode not in (0,2) or (not partial and (report.get('processing_status')!='COMPLETED' or report.get('source_errors'))):
                record.update(status='BLOCKED',message='An official source or processing step was blocked. Saved sources are retained; operator assistance may be needed.')
            else:
                record.update(status='COMPLETED_REVIEW_REQUIRED',message='Dataset ready. Uncertain quarterly flows withheld; accounting conflicts quarantined. Review input and delivered validation; not financially certified.',
                              result_ready=True,result_directory=report_path.parent.name,rows=report['organisation_quarters'],
                              columns=236,failed_accounting_checks=report['failed_accounting_checks'],unresolved_ownership=report['unresolved_ownership'])
                for key in ('quality_policy','upstream_organisation_quarters','financial_rows_quarantined',
                            'input_failed_accounting_checks','accounting_checks_passed','accounting_checks_not_testable',
                            'uncertain_quarter_values_withheld'):
                    record[key]=report.get(key)
                for key in ('requested_periods','delivered_periods','missing_periods','period_coverage'):
                    record[key]=report.get(key,[])
                if partial:
                    record.update(status='COMPLETED_PARTIAL_REVIEW_REQUIRED',message='Partial dataset ready. Some quarters or inputs are unavailable; review period coverage. No missing quarter was invented.')
                if progress.is_file():
                    for event in json.loads(progress.read_text(encoding='utf-8')).get('events',[]):
                        if event not in record['events']:record['events'].append(event)
        except TimeoutError:
            record.update(status='TIMED_OUT',message='Job exceeded the 30-minute pilot limit. Saved sources are retained.')
        except Exception:
            if child and child.poll() is None: child.kill();child.wait()
            record.update(status='FAILED',message='The job failed. Operator diagnostics remain private.')
        finally:
            record['finished_at_utc']=utc()
            if record['events'][-1]['stage']!=record['status']:record['events'].append({'stage':record['status'],'at':utc()})
            self.save(record)
            with self.lock:
                self.active=None
                if self.pending:
                    following=self.get(self.pending,public=False);self.pending=None;self.active=following['id']
                    threading.Thread(target=self.execute,args=(following,),daemon=True).start()

    def directory(self, job_id):
        record=self.get(job_id,public=False);name=record.get('result_directory','')
        if not record.get('result_ready') or not re.fullmatch(r'[A-Za-z0-9-]+',name): raise ValueError('Result is not ready')
        directory=self.root/'outputs/dataset'/name
        if directory.is_symlink() or not directory.is_dir(): raise ValueError('Invalid result directory')
        return directory


class PublicAPI:
    def __init__(self, root=ROOT, jobs=None, origins=None):
        self.root=Path(root);self.jobs=jobs or PublicJobs(root)
        self.origins=set(origins or [SITE])

    def __call__(self, env, respond):
        origin=env.get('HTTP_ORIGIN');method=env['REQUEST_METHOD'];path=env.get('PATH_INFO','')
        headers=[('Content-Type','application/json; charset=utf-8'),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff'),('Vary','Origin')]
        if origin in self.origins:
            headers += [('Access-Control-Allow-Origin',origin),('Access-Control-Allow-Methods','GET, POST, OPTIONS'),('Access-Control-Allow-Headers','Content-Type')]
        def finish(status, value, mime=None):
            body=value if isinstance(value,bytes) else json.dumps(value).encode()
            out=list(headers)
            if mime: out[0]=('Content-Type',mime)
            out.append(('Content-Length',str(len(body))));respond(status,out);return [body]
        if origin and origin not in self.origins: return finish('403 Forbidden',{'error':'Origin not permitted'})
        if method=='OPTIONS': return finish('204 No Content',b'')
        try:
            if method=='GET' and path=='/pilot/health':
                return finish('200 OK',{'status':'ok','mode':'TEMPORARY_LOCAL_PILOT','active_job':bool(self.jobs.active),'max_quarters':14,'supported_start':'20230331','supported_end':'20260630'})
            if method=='POST' and path=='/pilot/jobs':
                if origin not in self.origins: return finish('403 Forbidden',{'error':'Submit from the configured frontend'})
                length=int(env.get('CONTENT_LENGTH') or 0)
                if not 0<length<=1024: return finish('413 Content Too Large',{'error':'Request too large or empty'})
                if env.get('CONTENT_TYPE','').split(';')[0]!='application/json': raise ValueError('JSON required')
                return finish('202 Accepted',self.jobs.submit(json.loads(env['wsgi.input'].read(length))))
            match=re.fullmatch(r'/pilot/jobs/([0-9a-f]{32})(?:/(dataset|result|result-manifest|result-part|validation|validation-input|quarantine|periods|coverage|dictionary|provenance))?',path)
            if method=='GET' and match:
                job,kind=match.groups()
                if not kind: return finish('200 OK',self.jobs.get(job))
                directory=self.jobs.directory(job)
                if kind in ('result-manifest','result-part'):
                    # Bounded transfers avoid restarting a large CSV after a tunnel interruption.
                    # Cache the same formula-safe CSV representation used by the full result route.
                    cache=directory/'public_download.csv'
                    if not cache.exists():
                        temporary=directory/('public_download-'+uuid4().hex+'.tmp')
                        try:
                            with (directory/'organisation_financials.csv').open(encoding='utf-8',newline='') as source, temporary.open('w',encoding='utf-8-sig',newline='') as target:
                                writer=csv.writer(target)
                                for row in csv.reader(source):writer.writerow([safe_csv(v) for v in row])
                            os.replace(temporary,cache)
                        finally:
                            temporary.unlink(missing_ok=True)
                    size=cache.stat().st_size;chunk_size=1024*1024
                    if kind=='result-manifest':
                        with cache.open('rb') as handle:digest=hashlib.file_digest(handle,'sha256').hexdigest()
                        return finish('200 OK',{'bytes':size,'chunk_size':chunk_size,'parts':(size+chunk_size-1)//chunk_size,'sha256':digest})
                    query=parse_qs(env.get('QUERY_STRING',''))
                    if set(query)!={'index'} or len(query['index'])!=1:raise ValueError('Invalid part')
                    index=int(query['index'][0])
                    if not 0<=index<(size+chunk_size-1)//chunk_size:raise ValueError('Invalid part')
                    with cache.open('rb') as handle:
                        handle.seek(index*chunk_size);body=handle.read(chunk_size)
                    return finish('200 OK',body,'application/octet-stream')
                if kind=='dataset':
                    query=env.get('QUERY_STRING','')
                    if len(query)>2048: raise ValueError('Query too large')
                    params=parse_qs(query);params.pop('export',None)
                    page=int(params.get('page',['0'])[0])
                    if not 0<=page<=10000: raise ValueError('Invalid page')
                    return finish('200 OK',dataset(self.root,params,path=directory/'dataset.duckdb'))
                if kind in ('result','validation','validation-input','quarantine','periods','coverage'):
                    if kind=='result' and env.get('QUERY_STRING'):
                        query=env['QUERY_STRING']
                        if len(query)>2048:raise ValueError('Query too large')
                        params=parse_qs(query);params['export']=['1']
                        data=dataset(self.root,params,path=directory/'dataset.duckdb')
                        output=io.StringIO(newline='');writer=csv.writer(output);writer.writerow(data['columns'])
                        writer.writerows([safe_csv(r[c]) for c in data['columns']] for r in data['rows'])
                        return finish('200 OK',output.getvalue().encode('utf-8-sig'),'text/csv; charset=utf-8')
                    filename={'result':'organisation_financials.csv','validation':'validation.csv',
                              'validation-input':'validation_input.csv','quarantine':'financial_quarantine.csv','periods':'period_coverage.csv','coverage':'measure_coverage.csv'}[kind]
                    with (directory/filename).open(encoding='utf-8',newline='') as handle:
                        output=io.StringIO(newline='');writer=csv.writer(output)
                        for row in csv.reader(handle):writer.writerow([safe_csv(v) for v in row])
                    return finish('200 OK',output.getvalue().encode('utf-8-sig'),'text/csv; charset=utf-8')
                if kind=='dictionary':
                    mapping=json.loads((directory/'measure_dictionary.json').read_text(encoding='utf-8'))
                    with (directory/'organisation_financials.csv').open(encoding='utf-8-sig',newline='') as handle:
                        columns=next(csv.reader(handle))
                    return finish('200 OK',{'schema_version':'OUTPUT_DICTIONARY_V1','column_count':len(columns),
                                           'columns':build_dictionary(columns,mapping),'sources':mapping.get('sources',[])})
                if kind=='provenance':
                    report=json.loads((directory/'release_report.json').read_text(encoding='utf-8'))
                    allowed=['requested_start','requested_end','processing_status','organisation_quarters','duplicate_keys','unresolved_ownership','failed_accounting_checks','release_blockers','mapping_sha256',
                             'quality_policy','financial_rows_quarantined','input_failed_accounting_checks',
                             'accounting_checks_passed','accounting_checks_not_testable','uncertain_quarter_values_withheld']
                    allowed+=['requested_periods','delivered_periods','missing_periods','period_coverage']
                    public={k:report.get(k) for k in allowed}
                    public['source_issues']=[{'filename':s.get('filename'),'reason':s.get('reason','SOURCE_UNAVAILABLE_OR_INVALID')} for s in report.get('source_errors',[])]
                    public['sources']=[{k:s.get(k) for k in ('filename','period','source_url','sha256','retrieved_at_utc','acquisition')} for s in report['sources']]
                    return finish('200 OK',public)
            return finish('404 Not Found',{'error':'Route not found'})
        except KeyError:return finish('404 Not Found',{'error':'Job not found'})
        except RuntimeError as error:return finish('429 Too Many Requests',{'error':str(error)})
        except (ValueError,TypeError):return finish('422 Unprocessable Content',{'error':'Invalid request. Select 2023 Q1–2026 Q2; maximum 14 quarters. A completed result is required for downloads.'})
        except Exception:return finish('503 Service Unavailable',{'error':'Processor data unavailable; operator action required'})


if __name__=='__main__':
    from socketserver import ThreadingMixIn
    from wsgiref.simple_server import WSGIServer, make_server
    class Threaded(ThreadingMixIn,WSGIServer):daemon_threads=True
    origins=list(filter(None,os.environ.get('REGDATA_PUBLIC_ORIGINS',SITE).split(',')))
    print('Restricted local pilot: http://127.0.0.1:8770',flush=True)
    make_server('127.0.0.1',8770,PublicAPI(origins=origins),server_class=Threaded).serve_forever()
