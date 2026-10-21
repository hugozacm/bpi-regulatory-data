"""Bounded manual runner. A completed build is a review draft, never approval."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from backend_api import validate_request


def quarter_end(year, quarter):
    if not re.fullmatch(r'[0-9]{4}', str(year)) or str(quarter) not in ('1', '2', '3', '4'):
        raise ValueError('Use a four-digit year and quarter 1, 2, 3 or 4')
    return str(year) + ('0331', '0630', '0930', '1231')[int(quarter) - 1]


def collect(root, before, returncode, destination, limit=25 * 1024 * 1024):
    reports = set((root / 'outputs/dataset').glob('*/release_report.json')) - before
    if len(reports) != 1:
        raise ValueError('Expected exactly one new dataset report; no dataset exported')
    path = reports.pop()
    report = json.loads(path.read_text(encoding='utf-8'))
    shutil.copy2(path, destination / path.name)
    if returncode not in (0, 2) or report.get('processing_status') != 'COMPLETED' or report.get('source_errors'):
        raise ValueError('Processing blocked or sources incomplete; inspect release_report.json')
    names = ['organisation_financials.csv', 'organisation_financials.parquet',
             'validation.csv', 'measure_coverage.csv', 'ownership_ledger.csv']
    files = [path.parent / name for name in names]
    if any(not f.is_file() or f.is_symlink() for f in files):
        raise ValueError('Expected dataset files missing or unsafe')
    if sum(f.stat().st_size for f in files) + path.stat().st_size > limit:
        raise ValueError('Artifact exceeds 25 MiB cap; split into smaller ranges')
    hashes = {}
    for source in files:
        shutil.copy2(source, destination / source.name)
        hashes[source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
    return {'status': 'COMPLETED_REVIEW_REQUIRED', 'current_mvp_complete': False,
            'output_sha256': hashes, 'release_blockers': report.get('release_blockers', []),
            'note': 'Unfiltered upstream research draft, not the frozen approved/quarantined cohort. '
                    'Raw source bytes are not uploaded; source receipts remain in the release report.'}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--validate-only', action='store_true')
    a = p.parse_args(argv)
    root = a.root.resolve()
    destination = root / 'outputs/actions' / __import__('uuid').uuid4().hex
    destination.mkdir(parents=True)
    # Upload only this invocation, never an old successful result.
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as handle:
            handle.write(f'artifact_path={destination.as_posix()}\n')
    status = {'status': 'FAILED', 'current_mvp_complete': False}
    code = 1
    try:
        start = quarter_end(os.environ.get('FROM_YEAR', ''), os.environ.get('FROM_QUARTER', ''))
        end = quarter_end(os.environ.get('TO_YEAR', ''), os.environ.get('TO_QUARTER', ''))
        validate_request({'start': start, 'end': end}, root, max_quarters=4)
        status.update(start=start, end=end)
        if a.validate_only:
            status['status'] = 'VALIDATED_ONLY_NO_DOWNLOAD'
        else:
            before = set((root / 'outputs/dataset').glob('*/release_report.json'))
            result = subprocess.run([sys.executable, str(root / 'src/build_dataset.py'),
                                     '--root', str(root), '--start', start, '--end', end],
                                    cwd=root, timeout=1200, check=False)
            status.update(collect(root, before, result.returncode, destination))
        code = 0
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        status['error'] = str(error)
    (destination / 'job_status.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
    print(json.dumps(status, indent=2))
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as handle:
            handle.write('## Regulatory data job\n\n```json\n' + json.dumps(status, indent=2) + '\n```\n')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
