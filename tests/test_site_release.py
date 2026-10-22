import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
import pytest
from upload_site_assets import release_manifest


def test_manifest_is_content_addressed_and_excludes_private_config_and_stale_shards(tmp_path):
    (tmp_path/'quarters').mkdir()
    current='quarters/20230331-'+('a'*16)+'.json'
    (tmp_path/current).write_text('[]')
    (tmp_path/'quarters'/('20230331-'+('b'*16)+'.json')).write_text('[]')
    (tmp_path/'processor-config.json').write_text('{"ignored":true}')
    (tmp_path/'demo-data.json').write_text(json.dumps({'shards':{'20230331':current}}))
    (tmp_path/'index.html').write_text('<h1>Public</h1>')
    first,encoded,files,manifest=release_manifest(tmp_path)
    assert first==hashlib.sha256(encoded).hexdigest()
    assert 'processor-config.json' not in files and len(files)==3
    assert current in files
    (tmp_path/'index.html').write_text('<h1>Changed</h1>')
    assert release_manifest(tmp_path)[0]!=first


def test_manifest_rejects_unexpected_shard_path(tmp_path):
    (tmp_path/'demo-data.json').write_text('{"shards":{"bad":"../secret.json"}}')
    with pytest.raises(ValueError,match='Unexpected public shard'):release_manifest(tmp_path)
