"""Package the existing Site as a small Worker; preserve all public snapshot assets."""
import json
from pathlib import Path
import shutil
from serve_frontend import ROOT


def main():
    site=ROOT/'public_demo'
    manifest=site/'.openai/hosting.json'
    value=json.loads(manifest.read_text(encoding='utf-8'))
    value.pop('static',None)
    value.update(d1=None,r2='BUCKET')
    manifest.write_text(json.dumps(value,indent=2),encoding='utf-8')
    for folder in (site/'worker',site/'dist/server',site/'dist/.openai'):
        folder.mkdir(parents=True,exist_ok=True)
    source=ROOT/'hosting/connection-worker.mjs'
    shutil.copyfile(source,site/'worker/index.js')
    shutil.copyfile(source,site/'dist/server/index.js')
    shutil.copyfile(manifest,site/'dist/.openai/hosting.json')
    print('Existing Site packaged with stable discovery and public-asset storage.')


if __name__=='__main__':main()
