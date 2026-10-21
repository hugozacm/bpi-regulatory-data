"""Optional UI tests; install requirements-ui.txt first."""
import os
from pathlib import Path

import pytest

pytest.importorskip('streamlit')
from streamlit.testing.v1 import AppTest

APP = Path(__file__).parents[1] / 'app/streamlit_app.py'


def test_ui_opens_and_rejects_reversed_dates():
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not app.exception
    assert any('Earlier historical integration' in item.value for item in app.info)
    app.selectbox[0].set_value('20260630')
    app.selectbox[1].set_value('20230331')
    app.run()
    assert app.button[0].disabled
    assert not app.exception


@pytest.mark.skipif(os.environ.get('REGDATA_REAL_UI_TEST') != '1', reason='Explicit opt-in: uses real local cached sources')
def test_real_quarter_through_ui():
    app = AppTest.from_file(str(APP), default_timeout=180).run()
    app.selectbox[0].set_value('20240331')
    app.selectbox[1].set_value('20240331')
    app.checkbox[0].check()
    app.button[0].click().run(timeout=180)
    assert not app.exception
    assert any('COMPLETED' in item.value for item in app.markdown)
    assert any(item.label == 'Download selected-build CSV (review draft)' for item in app.get('download_button'))
