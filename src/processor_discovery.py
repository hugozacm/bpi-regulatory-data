"""Owner-only registration of the temporary address at the existing public Site."""
import hashlib
from pathlib import Path
import secrets
import requests

SITE='https://bpi-regulatory-research-hugo.amusedvine18.chatgpt.site'


def registration_key(root, create=False):
    path=Path(root)/'outputs/pilot_runtime/discovery.key'
    if create and not path.exists():
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('x',encoding='utf-8') as handle:
            handle.write(secrets.token_urlsafe(48))
    if not path.is_file():
        raise RuntimeError('Automatic discovery is not configured on this computer; see CONNECTED_FRONTEND.md')
    return path.read_text(encoding='utf-8').strip()


def register(root, origin, client=requests):
    response=client.put(SITE+'/_processor/connection',json={'api_origin':origin},
        headers={'Authorization':'Bearer '+registration_key(root)},timeout=20,allow_redirects=False)
    if response.status_code!=200 or response.json().get('registered') is not True:
        raise RuntimeError('Automatic registration failed; existing connection was preserved. Retry the launcher.')
    return True


def key_digest(root):
    return hashlib.sha256(registration_key(root,create=True).encode()).hexdigest()
