"""Package the existing Site as a small Worker; preserve all public snapshot assets."""
import json
import argparse
import re
from pathlib import Path
import shutil
from serve_frontend import ROOT


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release',help='Sealed asset release SHA-256; defaults to the latest local sealed receipt')
    parser.add_argument('--legacy-bridge',action='store_true',help='One-time migration: keep serving untouched legacy assets')
    args=parser.parse_args(argv)
    receipts=ROOT/'outputs/site_releases'
    if args.legacy_bridge:
        release=''
    else:
        candidates=sorted(receipts.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)
        release=args.release or (candidates[0].stem if candidates else '')
        if not re.fullmatch(r'[a-f0-9]{64}',release):parser.error('Stage and seal assets before building a release')
        receipt=receipts/(release+'.json')
        if not receipt.is_file() or json.loads(receipt.read_text()).get('sealed') is not True:
            parser.error('No sealed receipt for this release')
    site=ROOT/'public_demo'
    manifest=site/'.openai/hosting.json'
    value=json.loads(manifest.read_text(encoding='utf-8'))
    value.pop('static',None)
    value.update(d1=None,r2='BUCKET')
    manifest.write_text(json.dumps(value,indent=2),encoding='utf-8')
    for folder in (site/'worker',site/'dist/server',site/'dist/.openai'):
        folder.mkdir(parents=True,exist_ok=True)
    source=ROOT/'hosting/connection-worker.mjs'
    worker=source.read_text(encoding='utf-8').replace("const ASSET_RELEASE='';",f"const ASSET_RELEASE='{release}';")
    (site/'worker/index.js').write_text(worker,encoding='utf-8')
    (site/'dist/server/index.js').write_text(worker,encoding='utf-8')
    shutil.copyfile(manifest,site/'dist/.openai/hosting.json')
    print(json.dumps({'asset_release':release or 'legacy','rollback':'Deploy the prior saved Worker version to restore its pinned assets'}))


if __name__=='__main__':main()
