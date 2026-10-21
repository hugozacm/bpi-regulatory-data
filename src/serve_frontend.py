"""Read-only localhost research UI; never executes downloads or financial writes."""
import argparse
import csv
import io
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import duckdb

ROOT = Path(__file__).resolve().parents[1]


def latest(root, pattern):
    files = list(root.glob(pattern))
    return max(files, key=lambda p: p.parent.name) if files else None


def report(path):
    return json.loads(path.read_text(encoding='utf-8')) if path else None


def snapshot(root):
    return latest(root, 'outputs/mvp_v1/*/mvp_v1.duckdb')


def dataset(root, params, path=None):
    start, end = params.get('start', [''])[0], params.get('end', [''])[0]
    for bound in (start, end):
        if bound and (len(bound) != 8 or not bound.isdigit() or bound[4:] not in ('0331','0630','0930','1231')):
            raise ValueError('Range dates must be YYYYMMDD quarter ends')
    if start and end and start > end:
        raise ValueError('From quarter must not be after To quarter')
    path = path or snapshot(root)
    if not path:
        return {'rows': [], 'total': 0, 'columns': [], 'dates': [], 'bases': [], 'snapshot': None}
    page = max(0, int(params.get('page', ['0'])[0]))
    clauses, values = [], []
    for bound, operator in ((start, '>='), (end, '<=')):
        if bound:
            clauses.append('report_date ' + operator + ' ?')
            values.append(bound)
    search = params.get('search', [''])[0].strip()
    if search:
        clauses.append("(contains(lower(coalesce(name,'')), lower(?)) OR contains(entity_key, ?) OR contains(cast(top_rssd as varchar), ?))")
        values.extend([search] * 3)
    for field in ('report_date', 'basis'):
        value = params.get(field, [''])[0]
        if value:
            clauses.append(f'{field} = ?')
            values.append(value)
    where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
    with duckdb.connect(str(path), read_only=True) as con:
        columns = [r[0] for r in con.execute('DESCRIBE organisation_financials').fetchall()]
        # All values travel as strings, never lossy JavaScript financial numbers.
        projection = ','.join('cast("' + col.replace('"', '""') + '" as varchar) as "' + col.replace('"', '""') + '"' for col in columns)
        total = con.execute('SELECT count(*) FROM organisation_financials' + where, values).fetchone()[0]
        limit = '' if params.get('export') == ['1'] else ' LIMIT 50 OFFSET ?'
        query_values = values if not limit else values + [page * 50]
        rows = [dict(zip(columns, r)) for r in con.execute('SELECT ' + projection + ' FROM organisation_financials' + where + ' ORDER BY report_date, entity_key' + limit, query_values).fetchall()]
        dates = [r[0] for r in con.execute('SELECT DISTINCT report_date FROM organisation_financials ORDER BY report_date').fetchall()]
        bases = [r[0] for r in con.execute('SELECT DISTINCT basis FROM organisation_financials ORDER BY basis').fetchall()]
    return {'rows': rows, 'total': total, 'columns': columns, 'dates': dates, 'bases': bases, 'page': page,
            'snapshot': path.parent.name, 'page_size': 50}


def safe_csv(value):
    if value is None:
        return ''
    text = str(value)
    # Protect spreadsheet formula injection; leave signed integer financials intact.
    if text.lstrip().startswith(('=', '+', '-', '@')) and not text.lstrip('-').isdigit():
        return "'" + text
    return text


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, root=ROOT, **kwargs):
        self.root = root
        super().__init__(*args, directory=str(root / 'frontend'), **kwargs)

    def log_message(self, *args):
        pass

    def send_content(self, data, mime, status=200):
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self' http://127.0.0.1:8767; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        # No remote access, rebinding hostnames or arbitrary filesystem API.
        host = self.headers.get('Host', '').split(':')[0]
        if host not in ('localhost', '127.0.0.1'):
            self.send_content(b'Local access only', 'text/plain', 403)
            return
        url = urlparse(self.path)
        try:
            if url.path == '/api/status':
                db = snapshot(self.root)
                data = {'scope': report(self.root / 'config/delivery_scope.json'),
                        'interim': report(db.parent / 'mvp_manifest.json') if db else None,
                        'history': report(latest(self.root, 'outputs/history/*/history_report.json')),
                        'mode': 'Read-only local backend; no external data upload'}
                self.send_content(json.dumps(data).encode(), 'application/json')
            elif url.path in ('/api/dataset', '/api/export'):
                params = parse_qs(url.query)
                if url.path == '/api/export':
                    params['export'] = ['1']
                data = dataset(self.root, params)
                if url.path == '/api/export':
                    output = io.StringIO(newline='')
                    writer = csv.writer(output)
                    writer.writerow(data['columns'])
                    writer.writerows([safe_csv(row[col]) for col in data['columns']] for row in data['rows'])
                    self.send_content(output.getvalue().encode('utf-8-sig'), 'text/csv; charset=utf-8')
                else:
                    self.send_content(json.dumps(data).encode(), 'application/json')
            elif url.path in ('/', '/index.html', '/app.js', '/style.css', '/backend.js', '/backend-config.json'):
                name = 'index.html' if url.path == '/' else url.path.lstrip('/')
                content = (self.root / 'frontend' / name).read_bytes()
                mime = {'html': 'text/html', 'js': 'text/javascript', 'css': 'text/css', 'json': 'application/json'}[name.rsplit('.', 1)[-1]]
                self.send_content(content, mime + '; charset=utf-8')
            else:
                self.send_content(b'Not found', 'text/plain', 404)
        except (ValueError, OSError, duckdb.Error) as error:
            self.send_content(json.dumps({'error': str(error)}).encode(), 'application/json', 400)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), partial(Handler, root=ROOT))
    print(f'BPI local frontend: http://127.0.0.1:{args.port} (read-only)', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
