"""Add full raw-bank coverage, detailed exceptions and ownership audit to panel."""
import argparse
import json
from pathlib import Path
import duckdb
import pyarrow as pa
from bpi_pipeline import as_int, sha256
from history_audit import active_control_parents, ancestors, zip_rows, classify_events


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    a=p.parse_args()
    out=a.root/'outputs'/'panel_2023_2025'
    periods=[f'{y}{s}' for y in range(2023,2026) for s in ('0331','0630','0930','1231')]
    all_banks=[]
    audit=[]
    for period in periods:
        banks=[r['data'] for r in json.loads((a.root/'research'/f'fdic_extended_{period}.json').read_text())['data']]
        parents=active_control_parents(zip_rows(a.root/'research'/'CSV_RELATIONSHIPS.zip'),period)
        for b in banks:
            all_banks.append(b)
            rssd=as_int(b.get('RSSDID'))
            chain=ancestors(rssd,parents) if rssd else set()
            holder=as_int(b.get('RSSDHCR'))
            status=('MISSING_RSSD' if not rssd else
                'HOLDER_CONFIRMED_IN_NIC_CHAIN' if holder and holder != rssd and holder in chain else
                'FDIC_NIC_DISAGREEMENT_REVIEW' if holder and holder != rssd else
                'MISSING_FDIC_HOLDER_WITH_NIC_PARENT_REVIEW' if chain else
                'NO_CONTROL_PARENT_FOUND_IN_NIC')
            audit.append({'bank_cert':as_int(b['CERT']),'report_date':int(period),'bank_rssd':rssd,'fdic_holder':holder,'nic_ancestors':'|'.join(map(str,sorted(chain))),'status':status})
    with duckdb.connect(str(out/'panel.duckdb')) as con:
        con.register('raw_arrow',pa.Table.from_pylist(all_banks))
        con.execute('CREATE OR REPLACE TABLE bank_raw AS SELECT * FROM raw_arrow')
        con.register('audit_arrow',pa.Table.from_pylist(audit))
        con.execute('CREATE OR REPLACE TABLE ownership_audit AS SELECT * FROM audit_arrow')
        events=classify_events(list(zip_rows(a.root/'research'/'CSV_TRANSFORMATIONS.zip')),'20230101','20251231')
        con.register('events_arrow',pa.Table.from_pylist(events))
        con.execute('CREATE OR REPLACE TABLE merger_events AS SELECT * FROM events_arrow')
        con.execute('''CREATE OR REPLACE TABLE value_exceptions AS
            SELECT entity_key,report_date,measure,value_usd_thousands,
            CASE WHEN value_usd_thousands IS NULL THEN 'MISSING_VALUE' ELSE 'NEGATIVE_STOCK_REVIEW' END AS issue
            FROM measures WHERE value_usd_thousands IS NULL OR
            (measurement_type='stock' AND value_usd_thousands < 0)''')
        con.execute('''CREATE OR REPLACE TABLE organisation_financials AS
            SELECT i.name,i.entity_level,f.*,d.DEP AS bank_subsidiary_deposits,
            d.DEPDOM AS bank_subsidiary_domestic_deposits,
            d.DEPFOR AS bank_subsidiary_foreign_deposits,
            d.DEPIDOM AS bank_subsidiary_domestic_interest_bearing,
            d.DEPNIDOM AS bank_subsidiary_domestic_noninterest_bearing,
            d.bank_count,d.bank_sum_minus_core,
            'REVIEW_REQUIRED' AS release_status
            FROM financials_wide f JOIN institutions i USING(entity_key,report_date)
            LEFT JOIN deposits d USING(entity_key,report_date)
            LEFT JOIN ownership_audit a ON a.bank_cert=try_cast(i.fdic_cert AS BIGINT) AND a.report_date=try_cast(i.report_date AS BIGINT)
            WHERE i.entity_level='consolidated_BHC' OR a.status='NO_CONTROL_PARENT_FOUND_IN_NIC' ''')
        con.execute('''CREATE OR REPLACE TABLE merger_quarter_review AS
            SELECT DISTINCT f.entity_key,f.report_date,e.ID_RSSD_PREDECESSOR,e.ID_RSSD_SUCCESSOR,e.DT_TRANS,
            'Verify economic consolidation date and YTD flow comparability; NIC date alone is insufficient' AS issue
            FROM organisation_financials f JOIN merger_events e
            ON f.entity_key IN ('BHC_RSSD_' || e.ID_RSSD_PREDECESSOR,'BHC_RSSD_' || e.ID_RSSD_SUCCESSOR)
            AND date_trunc('quarter',strptime(cast(f.report_date AS VARCHAR),'%Y%m%d'))=
                date_trunc('quarter',strptime(e.DT_TRANS,'%Y%m%d'))''')
        for table in ('bank_raw','ownership_audit','value_exceptions','organisation_financials','merger_events','merger_quarter_review'):
            con.execute(f"COPY {table} TO ? (HEADER, DELIMITER ',')",[str(out/f'{table}.csv')])
            con.execute(f'COPY {table} TO ? (FORMAT PARQUET, COMPRESSION ZSTD)',[str(out/f'{table}.parquet')])
        result={
            'quarters':12,
            'organisation_quarters':con.execute('select count(*) from organisation_financials').fetchone()[0],
            'bank_quarters_retained':con.execute('select count(*) from bank_raw').fetchone()[0],
            'value_exception_counts':con.execute('select issue,count(*) from value_exceptions group by issue').fetchall(),
            'ownership_status_counts':con.execute('select status,count(*) from ownership_audit group by status').fetchall(),
            'coverage_counts':con.execute('select status,count(*) from bank_coverage group by status').fetchall(),
            'duplicate_organisation_periods':con.execute('select count(*) from (select entity_key,report_date from organisation_financials group by all having count(*)>1)').fetchone()[0],
            'merger_adjusted_history':'NOT_YET_APPROVED_OR_PRODUCED',
            'nic_relationships_sha256':sha256(a.root/'research'/'CSV_RELATIONSHIPS.zip'),
            'nic_transformations_sha256':sha256(a.root/'research'/'CSV_TRANSFORMATIONS.zip'),
            'status':'REVIEW_REQUIRED'}
        (out/'review_summary.json').write_text(json.dumps(result,indent=2))
        (out/'REVIEW_REQUIRED.txt').write_text('Research draft. Full-population validation exceptions, unresolved reporting perimeters and merger adjustment remain outstanding. See PANEL_STATUS.md.\n')
        print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
