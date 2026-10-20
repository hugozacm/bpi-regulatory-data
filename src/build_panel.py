"""Reproduce every 2023-2025 quarter, retaining all validation exceptions."""
import argparse
import json
from pathlib import Path
import duckdb
from bpi_pipeline import main as run_quarter, download_fdic, load_fdic_json, sha256


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    a = p.parse_args()
    research = a.root/'research'
    output = a.root/'outputs'/'panel_2023_2025'
    output.mkdir(parents=True, exist_ok=True)
    periods = [f'{year}{suffix}' for year in range(2023,2026) for suffix in ('0331','0630','0930','1231')]
    reports=[]
    for index, period in enumerate(periods):
        prior = periods[index-1] if index else '20221231'
        current_fdic = research/f'fdic_extended_{period}.json'
        if not current_fdic.exists():
            download_fdic(period,current_fdic)
        load_fdic_json(current_fdic)
        summary=run_quarter(['--period',period,'--prior-period',prior,'--all-bhcs','--all-bank-candidates',
            '--y9-current',str(research/f'BHCF{period}.ZIP'),'--y9-prior',str(research/f'BHCF{prior}.ZIP'),
            '--fdic-current',str(current_fdic),'--fdic-prior',str(research/f'fdic_extended_{prior}.json'),
            '--output',str(output/period)])
        reports.append(summary)
        (output/'quarter_summary.json').write_text(json.dumps(reports,indent=2))
        print('Completed quarter',period,flush=True)
    con=duckdb.connect(str(output/'panel.duckdb'))
    for table in ('financials_wide','institutions','measures','ownership','deposits','validation','provenance','bank_coverage'):
        paths=[str(output/period/f'{table}.parquet') for period in periods]
        con.execute(f'CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_parquet(?, union_by_name=true)',[paths])
        con.execute(f"COPY {table} TO ? (HEADER, DELIMITER ',')",[str(output/f'{table}.csv')])
        con.execute(f'COPY {table} TO ? (FORMAT PARQUET, COMPRESSION ZSTD)',[str(output/f'{table}.parquet')])
    count=con.execute('select count(*) from financials_wide').fetchone()[0]
    con.close()
    print(json.dumps({'quarters':len(periods),'organisation_quarters':count,'status':'REVIEW_REQUIRED'},indent=2))


if __name__=='__main__':
    main()
