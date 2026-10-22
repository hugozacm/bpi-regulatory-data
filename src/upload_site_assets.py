"""Publish only the existing allowlisted public export, never project or source files."""
import concurrent.futures
import mimetypes
import re
import requests
from processor_discovery import SITE, registration_key
from serve_frontend import ROOT


def main():
    folder=ROOT/'public_demo/dist'
    files=[p for p in folder.rglob('*') if p.is_file() and
           re.fullmatch(r'(?:[a-z0-9-]+\.(?:html|js|css|json)|quarters/\d{8}-[a-f0-9]{16}\.json)',p.relative_to(folder).as_posix()) and
           p.name!='processor-config.json']
    key=registration_key(ROOT)
    def upload(path):
        headers={'Authorization':'Bearer '+key,'Content-Type':mimetypes.guess_type(path.name)[0] or 'application/octet-stream'}
        for attempt in range(3):
            try:
                with path.open('rb') as handle:
                    response=requests.put(SITE+'/_processor/asset',params={'key':path.relative_to(folder).as_posix()},
                        data=handle,headers=headers,timeout=60,allow_redirects=False)
                response.raise_for_status()
                return path.name
            except requests.RequestException:
                if attempt==2:raise
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for name in pool.map(upload,files):print('Published',name,flush=True)


if __name__=='__main__':main()
