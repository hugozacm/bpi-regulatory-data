"""Stage checksum-verified immutable assets; deployment alone selects the release."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import re
import requests
from processor_discovery import SITE, registration_key
from serve_frontend import ROOT


def release_manifest(folder):
    folder=Path(folder)
    files={p.name:p for p in folder.iterdir() if p.is_file() and
           re.fullmatch(r'[a-z0-9-]+\.(?:html|js|css|json)',p.name) and p.name!='processor-config.json'}
    meta=json.loads((folder/'demo-data.json').read_text(encoding='utf-8'))
    for name in meta['shards'].values():
        if not re.fullmatch(r'quarters/\d{8}-[a-f0-9]{16}\.json',name):
            raise ValueError('Unexpected public shard path')
        files[name]=folder/name
    manifest={'schema':'SITE_ASSET_RELEASE_V1','files':{name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in sorted(files.items())}}
    encoded=json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(encoded).hexdigest(),encoded,files,manifest


def main():
    release,encoded,files,manifest=release_manifest(ROOT/'public_demo/dist')
    key=registration_key(ROOT)
    def upload(item):
        name,path=item
        headers={'Authorization':'Bearer '+key,'X-Asset-SHA256':manifest['files'][name]}
        for attempt in range(3):
            try:
                with path.open('rb') as handle:
                    response=requests.put(SITE+'/_processor/asset',params={'release':release,'key':name},
                        data=handle,headers=headers,timeout=60,allow_redirects=False)
                response.raise_for_status()
                return name
            except requests.RequestException:
                if attempt==2:raise
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for name in pool.map(upload,files.items()):print('Staged',name,flush=True)
    response=requests.put(SITE+'/_processor/seal',params={'release':release},data=encoded,
        headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},timeout=30,allow_redirects=False)
    response.raise_for_status()
    if response.json().get('sealed') is not True:raise RuntimeError('Release was not sealed; do not deploy')
    receipt=ROOT/'outputs/site_releases'/(release+'.json');receipt.parent.mkdir(parents=True,exist_ok=True)
    receipt.write_text(json.dumps({'sealed':True,'release':release,'files':manifest['files']},indent=2),encoding='utf-8')
    print(json.dumps({'sealed':True,'release':release,'note':'Live assets unchanged until this release is pinned in a deployment.'}))


if __name__=='__main__':main()
