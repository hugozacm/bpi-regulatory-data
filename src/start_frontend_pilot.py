"""Start the restricted local processor and a fresh temporary HTTPS tunnel; no paid account."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import requests
from processor_discovery import register

ROOT=Path(__file__).resolve().parents[1]
URL='https://github.com/cloudflare/cloudflared/releases/download/2026.10.3/cloudflared-windows-amd64.exe'
DIGEST='76b2805253d0d6ffacb092a7acfbee99e7af6917835c0c5410e23f3ef5052da2'


def main():
    if sys.platform!='win32':raise SystemExit('This pilot launcher is currently Windows-only')
    runtime=ROOT/'outputs/pilot_runtime';runtime.mkdir(parents=True,exist_ok=True)
    executable=runtime/'cloudflared.exe'
    if not executable.is_file():
        response=requests.get(URL,timeout=90);response.raise_for_status()
        if hashlib.sha256(response.content).hexdigest()!=DIGEST:raise ValueError('Official binary checksum mismatch')
        executable.write_bytes(response.content)
    if hashlib.sha256(executable.read_bytes()).hexdigest()!=DIGEST:raise ValueError('Tunnel binary was modified; refusing to execute')
    flags=subprocess.CREATE_NO_WINDOW
    processes={}
    def verify_local():
        response=requests.get('http://127.0.0.1:8770/pilot/health',timeout=3)
        response.raise_for_status()
        health=response.json()
        if health.get('status')!='ok' or health.get('mode')!='TEMPORARY_LOCAL_PILOT':
            raise RuntimeError('Port 8770 belongs to an unexpected service; refusing to expose it')
    try:
        verify_local()
    except requests.RequestException:
        with (runtime/'processor.stdout.log').open('ab') as out,(runtime/'processor.stderr.log').open('ab') as err:
            process=subprocess.Popen([sys.executable,str(ROOT/'src/public_processor.py')],cwd=ROOT,stdout=out,stderr=err,creationflags=flags)
        processes['processor_pid']=process.pid
        for _ in range(20):
            try:verify_local();break
            except requests.RequestException:time.sleep(.5)
        else:raise RuntimeError('Local processor did not start; inspect logs')
    # Reuse a healthy existing connection rather than creating a tunnel per click.
    for receipt in sorted(runtime.glob('connection-*.json'),reverse=True):
        previous=json.loads(receipt.read_text(encoding='utf-8'))
        origin=previous.get('api_origin','')
        if not re.fullmatch(r'https://[a-z0-9-]+\.trycloudflare\.com',origin):continue
        try:
            response=requests.get(origin+'/pilot/health',timeout=3)
            health=response.json()
            if response.ok and health.get('status')=='ok' and health.get('mode')=='TEMPORARY_LOCAL_PILOT':
                register(ROOT,origin)
                print(json.dumps({'api_origin':origin,'automatic_discovery':True,'reused_connection':True,
                    'note':'Website connected automatically. Keep the computer awake.'},indent=2));return
        except (requests.RequestException,ValueError):pass
    suffix=str(time.time_ns())
    tunnel_log=runtime/('tunnel-'+suffix+'.log')
    with tunnel_log.open('wb') as handle:
        tunnel=subprocess.Popen([str(executable),'tunnel','--url','http://127.0.0.1:8770','--no-autoupdate','--protocol','http2'],
                                 cwd=ROOT,stdout=handle,stderr=subprocess.STDOUT,creationflags=flags)
    processes['tunnel_pid']=tunnel.pid
    for _ in range(60):
        urls=re.findall(r'https://[a-z0-9-]+\.trycloudflare\.com',tunnel_log.read_text(encoding='utf-8',errors='replace'))
        if urls:
            origin=urls[-1]
            try:
                result=requests.get(origin+'/pilot/health',timeout=5)
                health=result.json()
                if result.ok and health.get('status')=='ok' and health.get('mode')=='TEMPORARY_LOCAL_PILOT':
                    info={**processes,'api_origin':origin,'automatic_discovery':True,'note':'Website connects automatically. Keep the computer and tunnel running.'}
                    (runtime/('connection-'+suffix+'.json')).write_text(json.dumps(info,indent=2),encoding='utf-8')
                    register(ROOT,origin)
                    print(json.dumps(info,indent=2));return
            except requests.RequestException:pass
        if tunnel.poll() is not None:break
        time.sleep(1)
    tunnel.terminate()
    raise RuntimeError('Temporary tunnel did not become available; inspect local runtime logs')


if __name__=='__main__':main()
