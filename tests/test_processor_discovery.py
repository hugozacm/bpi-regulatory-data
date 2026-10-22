import hashlib
from pathlib import Path
import pytest
import sys
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from processor_discovery import SITE, registration_key, key_digest, register


def test_key_is_stable_and_missing_setup_is_explicit(tmp_path):
    with pytest.raises(RuntimeError,match='not configured'):registration_key(tmp_path)
    first=key_digest(tmp_path)
    assert len(registration_key(tmp_path))>=48
    assert first==key_digest(tmp_path)==hashlib.sha256(registration_key(tmp_path).encode()).hexdigest()


def test_registration_uses_only_site_and_never_follows_redirects(tmp_path):
    key_digest(tmp_path)
    class Client:
        def put(self,url,**kwargs):
            assert url==SITE+'/_processor/connection'
            assert kwargs['json']=={'api_origin':'https://example.trycloudflare.com'}
            assert kwargs['headers']['Authorization']=='Bearer '+registration_key(tmp_path)
            assert kwargs['allow_redirects'] is False
            return type('Response',(),{'status_code':200,'json':lambda self:{'registered':True}})()
    assert register(tmp_path,'https://example.trycloudflare.com',Client())


def test_failed_registration_is_not_reported_successful(tmp_path):
    key_digest(tmp_path)
    class Client:
        def put(self,*args,**kwargs):return type('Response',(),{'status_code':401})()
    with pytest.raises(RuntimeError,match='registration failed'):register(tmp_path,'https://example.trycloudflare.com',Client())


def test_launcher_reuses_healthy_tunnel_and_registers_without_copying_link(tmp_path,monkeypatch):
    import start_frontend_pilot as launcher
    runtime=tmp_path/'outputs/pilot_runtime';runtime.mkdir(parents=True)
    (runtime/'cloudflared.exe').write_bytes(b'test-only-binary')
    (runtime/'connection-1.json').write_text('{"api_origin":"https://existing.trycloudflare.com"}')
    monkeypatch.setattr(launcher,'ROOT',tmp_path)
    monkeypatch.setattr(launcher,'DIGEST',hashlib.sha256(b'test-only-binary').hexdigest())
    monkeypatch.setattr(launcher.sys,'platform','win32')
    class Response:
        ok=True
        def raise_for_status(self):pass
        def json(self):return {'status':'ok','mode':'TEMPORARY_LOCAL_PILOT'}
    monkeypatch.setattr(launcher.requests,'get',lambda *a,**k:Response())
    monkeypatch.setattr(launcher.subprocess,'Popen',lambda *a,**k:pytest.fail('Healthy tunnel must be reused'))
    calls=[]
    monkeypatch.setattr(launcher,'register',lambda root,origin:calls.append(origin))
    launcher.main()
    assert calls==['https://existing.trycloudflare.com']
