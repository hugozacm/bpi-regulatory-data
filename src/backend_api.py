"""WSGI API for public snapshot reads and operator-only bounded build jobs.

Local runner is for development. Deploy behind HTTPS using one WSGI worker.
Never place REGDATA_OPERATOR_KEY in a browser bundle or source repository.
"""
import csv
import io
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs
from uuid import uuid4

import duckdb

from build_dataset import quarters
from serve_frontend import ROOT, dataset, latest, report, safe_csv, snapshot


def validate_request(body, root, max_quarters=12):
    if not isinstance(body, dict) or set(body) != {'start', 'end'}:
        raise ValueError('Provide exactly start and end quarter-end dates')
    start, end = body['start'], body['end']
    if not all(isinstance(v, str) and re.fullmatch(r'\d{4}(0331|0630|0930|1231)', v) for v in (start, end)):
        raise ValueError('Use YYYYMMDD quarter ends')
    periods = quarters(start, end)
    if len(periods) > max_quarters:
        raise ValueError(f'At most {max_quarters} quarters per processing job')
    fields = json.loads((root / 'config/expanded_measures.json').read_text(encoding='utf-8'))['fields']
    if any(start < f['valid_from'] or end > f['valid_to'] for f in fields):
        raise ValueError('Historical financial mappings are not implemented for this range; no processing job was started')
    return start, end


class Jobs:
    def __init__(self, root, runner=None):
        self.root = root
        self.runner = runner or subprocess.run
        self.lock = threading.Lock()
        self.active = None
        self.last_started = float('-inf')
        self.directory = root / 'outputs/api_jobs'
        self.records = {}

    def save(self, record):
        self.directory.mkdir(parents=True, exist_ok=True)
        temp = self.directory / (record['id'] + '.tmp')
        temp.write_text(json.dumps(record, indent=2), encoding='utf-8')
        temp.replace(self.directory / (record['id'] + '.json'))
        self.records[record['id']] = dict(record)

    def get(self, job_id):
        if not re.fullmatch(r'[0-9a-f]{32}', job_id):
            raise KeyError(job_id)
        with self.lock:
            if job_id in self.records:
                return dict(self.records[job_id])
            path = self.directory / (job_id + '.json')
            if not path.is_file():
                raise KeyError(job_id)
            saved = json.loads(path.read_text(encoding='utf-8'))
            if saved['status'] in ('QUEUED', 'RUNNING'):
                saved['status'] = 'INTERRUPTED'
                saved['message'] = 'Backend restarted; submit a new job to resume from cached sources'
            return saved

    def submit(self, body):
        start, end = validate_request(body, self.root)
        with self.lock:
            if self.active:
                raise RuntimeError('A processing job is already running')
            if time.monotonic() - self.last_started < 60:
                raise RuntimeError('Wait at least 60 seconds between processing jobs')
            record = {'id': uuid4().hex, 'start': start, 'end': end, 'status': 'QUEUED',
                      'created_at_utc': datetime.now(timezone.utc).isoformat(),
                      'message': 'Waiting to acquire and process sources', 'result_ready': False,
                      'financially_certified': False, 'historical_mvp_complete': False}
            self.save(record)
            self.active = record['id']
            self.last_started = time.monotonic()
        threading.Thread(target=self.execute, args=(record,), daemon=True).start()
        return dict(record)

    def execute(self, record):
        # One builder process, fixed script and argument list; no shell/user paths.
        try:
            with self.lock:
                record.update(status='RUNNING', message='Acquiring sources and building the research draft')
                self.save(record)
            before = set((self.root / 'outputs/dataset').glob('*/release_report.json'))
            with (self.directory / (record['id'] + '.log')).open('w', encoding='utf-8') as log:
                completed = self.runner([sys.executable, str(self.root / 'src/build_dataset.py'),
                    '--root', str(self.root), '--start', record['start'], '--end', record['end']],
                    cwd=str(self.root), stdout=log, stderr=subprocess.STDOUT, timeout=1800,
                    check=False)
            candidates = set((self.root / 'outputs/dataset').glob('*/release_report.json')) - before
            if len(candidates) != 1:
                raise ValueError('Expected exactly one build report')
            source = candidates.pop()
            build = report(source)
            if build.get('processing_status') == 'COMPLETED' and not build.get('source_errors') and completed.returncode in (0, 2):
                record.update(status='COMPLETED_REVIEW_REQUIRED', message='Research build finished; financial and coverage review still required',
                              result_ready=True, result_directory=source.parent.name,
                              rows=build.get('organisation_quarters'),
                              failed_accounting_checks=build.get('failed_accounting_checks'))
            else:
                record.update(status='BLOCKED', message='Source acquisition or processing blocked; operator must inspect the private job log')
        except subprocess.TimeoutExpired:
            record.update(status='TIMED_OUT', message='Processing exceeded the 30-minute job limit')
        except Exception:
            record.update(status='FAILED', message='Build failed; inspect the private operator log and source reports')
        finally:
            with self.lock:
                record['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
                self.save(record)
                self.active = None

    def result_file(self, job_id):
        record = self.get(job_id)
        name = record.get('result_directory', '')
        if not record.get('result_ready') or not re.fullmatch(r'[0-9A-Za-z-]+', name):
            raise ValueError('No completed research result for this job')
        return self.root / 'outputs/dataset' / name / 'organisation_financials.csv'


class API:
    def __init__(self, root=ROOT, key=None, origins=None, jobs=None):
        self.root = root
        self.key = os.environ.get('REGDATA_OPERATOR_KEY', '') if key is None else key
        self.origins = set(origins if origins is not None else filter(None, os.environ.get('REGDATA_ALLOWED_ORIGINS', '').split(',')))
        self.jobs = jobs or Jobs(root)

    def __call__(self, env, respond):
        origin = env.get('HTTP_ORIGIN')
        headers = [('Content-Type','application/json; charset=utf-8'), ('Cache-Control','no-store'),
                   ('X-Content-Type-Options','nosniff'), ('Vary','Origin')]
        if origin and origin in self.origins:
            headers.extend([('Access-Control-Allow-Origin',origin),('Access-Control-Allow-Headers','Authorization, Content-Type'),
                            ('Access-Control-Allow-Methods','GET, POST, OPTIONS')])
        def finish(code, value, mime=None):
            phrases = {200:'OK',202:'Accepted',204:'No Content',400:'Bad Request',401:'Unauthorized',403:'Forbidden',404:'Not Found',409:'Conflict',413:'Content Too Large',422:'Unprocessable Content',429:'Too Many Requests',503:'Service Unavailable'}
            body = value if isinstance(value, bytes) else json.dumps(value).encode()
            result_headers = list(headers)
            if mime:
                result_headers[0] = ('Content-Type',mime)
            result_headers.append(('Content-Length',str(len(body))))
            respond(f'{code} {phrases[code]}',result_headers)
            return [body]
        if origin and origin not in self.origins:
            return finish(403, {'error':'Origin is not permitted'})
        method, path = env['REQUEST_METHOD'], env.get('PATH_INFO','')
        if method == 'OPTIONS':
            return finish(204,b'')
        if path.startswith('/api/jobs'):
            if not self.key or len(self.key) < 32:
                return finish(503, {'error':'Operator processing is not configured'})
            if not secrets.compare_digest(env.get('HTTP_AUTHORIZATION',''), 'Bearer '+self.key):
                return finish(401, {'error':'Operator authorisation required'})
        try:
            if method == 'GET' and path == '/api/health':
                return finish(200, {'status':'ok','processing_enabled':len(self.key)>=32,'historical_mvp_complete':False})
            if method == 'GET' and path == '/api/status':
                db = snapshot(self.root)
                m = report(db.parent / 'mvp_manifest.json') if db else {}
                allowed = ['rows','columns','periods','financial_tests_passed','financial_tests_failed','financial_tests_not_testable','financial_tests_failed_input','financial_rows_quarantined','additional_bank_only_groups_excluded','unresolved_ownership_records','uncertain_quarter_values_withheld']
                h = report(latest(self.root,'outputs/history/*/history_report.json')) or {}
                history_keys = ['status','reported_values','periods_loaded','missing_requested_periods','requested_coverage_complete','limitations']
                return finish(200, {'interim':{k:m[k] for k in allowed if k in m},
                    'history':{k:h[k] for k in history_keys if k in h},
                    'mode':'Python read-only snapshot API; processing requires operator authorisation',
                    'processing_enabled':len(self.key)>=32, 'historical_mvp_complete':False})
            if method == 'GET' and path in ('/api/dataset','/api/export'):
                params = parse_qs(env.get('QUERY_STRING',''))
                if path.endswith('export'):
                    params['export']=['1']
                data = dataset(self.root,params)
                if path.endswith('export'):
                    output=io.StringIO(newline=''); writer=csv.writer(output)
                    writer.writerow(data['columns'])
                    writer.writerows([safe_csv(row[c]) for c in data['columns']] for row in data['rows'])
                    return finish(200,output.getvalue().encode('utf-8-sig'),'text/csv; charset=utf-8')
                return finish(200,data)
            if method == 'POST' and path == '/api/jobs':
                if env.get('CONTENT_TYPE','').split(';')[0] != 'application/json':
                    return finish(400,{'error':'application/json required'})
                length=int(env.get('CONTENT_LENGTH') or 0)
                if not 0 < length <= 1024:
                    return finish(413,{'error':'Request must contain 1–1024 bytes'})
                return finish(202,self.jobs.submit(json.loads(env['wsgi.input'].read(length))))
            if method == 'GET' and re.fullmatch(r'/api/jobs/[0-9a-f]{32}(?:/result)?',path):
                job_id=path.split('/')[3]
                if path.endswith('/result'):
                    # Result remains an upstream draft, not silently published as MVP.
                    with self.jobs.result_file(job_id).open(encoding='utf-8',newline='') as handle:
                        rows=csv.reader(handle); output=io.StringIO(newline=''); writer=csv.writer(output)
                        writer.writerows([safe_csv(v) for v in row] for row in rows)
                    return finish(200,output.getvalue().encode('utf-8-sig'),'text/csv; charset=utf-8')
                public={k:v for k,v in self.jobs.get(job_id).items() if k!='result_directory'}
                return finish(200,public)
            return finish(404,{'error':'Route not found'})
        except KeyError:
            return finish(404,{'error':'Job not found'})
        except RuntimeError as error:
            return finish(429,{'error':str(error)})
        except (ValueError, TypeError):
            return finish(422,{'error':'Invalid request or unsupported date range. Financial mappings currently support 2023 Q1–2026 Q2; maximum 12 quarters per job.'})
        except (OSError, duckdb.Error):
            return finish(503,{'error':'Local data unavailable; operator action required'})


application = API()

if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    port = int(os.environ.get('PORT','8767'))
    print(f'Development API: http://127.0.0.1:{port}',flush=True)
    make_server('127.0.0.1',port,application).serve_forever()
