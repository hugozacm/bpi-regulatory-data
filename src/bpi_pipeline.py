from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import zipfile
from decimal import Decimal
from calendar import monthrange
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import requests


FDIC_API = "https://api.fdic.gov/banks/financials"
FDIC_FIELDS = [
    "CERT", "REPDTE", "NAME", "ASSET", "LNLSNET", "DEP", "EQ",
    "NETINC", "NETINCQ", "RSSDID", "RSSDHCR", "NAMEHCR", "STALP",
    "DEPDOM", "DEPFOR", "DEPIDOM", "DEPNIDOM",
]
Y9_FIELDS = [
    "RSSD9001", "RSSD9999", "BHCK2170", "BHCK2122", "BHCK3210",
    "BHCK4340", "BHDM6631", "BHDM6636", "BHFN6631", "BHFN6636",
]
Y9_URL = (
    "https://www.ffiec.gov/npw/FinancialReport/ReturnBHCFZipFiles"
    "?zipfilename=BHCF{period}.ZIP"
)


def as_int(value):
    if value in (None, "", "null", "None"):
        return None
    number = Decimal(str(value))
    if not number.is_finite() or number != number.to_integral_value():
        raise ValueError(f"Expected an integral regulatory amount or ID: {value}")
    return int(number)


def validate_period_pair(current, prior):
    def parse(value):
        date = datetime.strptime(value, "%Y%m%d")
        if date.month not in (3, 6, 9, 12) or date.day != monthrange(date.year, date.month)[1]:
            raise ValueError("Reporting dates must be calendar quarter ends")
        return date
    now, prev = parse(current), parse(prior)
    expected_month = now.month - 3 if now.month > 3 else 12
    expected_year = now.year if now.month > 3 else now.year - 1
    if (prev.year, prev.month) != (expected_year, expected_month):
        raise ValueError("Prior period must be the immediately preceding quarter")


def validate_records(rows, id_field, date_field, period):
    ids = [as_int(row.get(id_field)) for row in rows]
    if not rows or None in ids or len(ids) != len(set(ids)):
        raise ValueError(f"Empty input, missing or duplicate {id_field}")
    if any(str(row.get(date_field)) != period for row in rows):
        raise ValueError(f"Input {date_field} does not match requested {period}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def optional_prior_hash(path, period):
    return '' if period[4:6] == '03' else sha256(path)


def load_y9(path: Path, fields=None) -> list[dict]:
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".txt")]
        if len(members) != 1:
            raise ValueError(f"Expected one TXT file in {path}, found {members}")
        with archive.open(members[0]) as raw:
            import io
            text = io.TextIOWrapper(raw, encoding="latin-1", newline="")
            # NIC uses caret-separated records, not RFC CSV quoting. Free-text
            # quotation marks must not swallow subsequent physical records.
            reader = csv.DictReader(text, delimiter="^", quoting=csv.QUOTE_NONE)
            missing = sorted(set(Y9_FIELDS) - set(reader.fieldnames or []))
            if missing:
                raise ValueError(f"Missing expected FR Y-9C columns: {missing}")
            rows = []
            for row in reader:
                if None in row or any(v is None for v in row.values()):
                    raise ValueError(f"Ragged NIC input record at line {reader.line_num}")
                # The mixed NIC file also contains Y-9LP/Y-9SP rows. A populated
                # BHCK2170 is the conservative, observable Y-9C inclusion test.
                if row.get("BHCK2170") in (None, ""):
                    continue
                rows.append({field: row.get(field, "") for field in (fields or Y9_FIELDS)})
            return rows


def load_fdic_json(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if len(payload["data"]) != int(payload["meta"]["total"]):
        raise ValueError("Incomplete FDIC response: downloaded rows differ from meta.total")
    return [entry["data"] for entry in payload["data"]]


def download_fdic(period: str, path: Path) -> None:
    params = {
        "filters": f"REPDTE:{period}",
        "fields": ",".join(FDIC_FIELDS),
        "limit": 10000,
        "format": "json",
        "sort_by": "ASSET",
        "sort_order": "DESC",
    }
    response = requests.get(FDIC_API, params=params, timeout=120)
    response.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)


def deposits_y9(row: dict) -> int | None:
    values = [as_int(row.get(field)) for field in ("BHDM6631", "BHDM6636", "BHFN6631", "BHFN6636")]
    return None if any(value is None for value in values) else sum(values)


def quarter_from_ytd(period: str, current, prior):
    current = as_int(current)
    if current is None:
        return None
    month = int(period[4:6])
    if month == 3:
        return current
    prior = as_int(prior)
    return None if prior is None else current - prior


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description="BPI regulatory-data MVP")
    parser.add_argument("--period", default="20241231")
    parser.add_argument("--prior-period", default="20240930")
    parser.add_argument("--y9-current", type=Path, required=True)
    parser.add_argument("--y9-prior", type=Path, required=True)
    parser.add_argument("--fdic-current", type=Path)
    parser.add_argument("--fdic-prior", type=Path)
    parser.add_argument("--output", type=Path, default=Path("outputs/20241231"))
    parser.add_argument("--bhcs", type=int, default=5)
    parser.add_argument("--standalone-banks", type=int, default=3)
    parser.add_argument("--all-bhcs", action="store_true", help="Include all observed Y-9C filers")
    parser.add_argument("--all-bank-candidates", action="store_true", help="Retain all blank/self-holder bank candidates, including missing financials")
    args = parser.parse_args(argv)
    validate_period_pair(args.period, args.prior_period)

    args.output.mkdir(parents=True, exist_ok=True)
    raw = args.output / "raw"
    raw.mkdir(exist_ok=True)
    fdic_current = args.fdic_current or raw / f"fdic_{args.period}.json"
    fdic_prior = args.fdic_prior or raw / f"fdic_{args.prior_period}.json"
    if not fdic_current.exists():
        download_fdic(args.period, fdic_current)
    if not fdic_prior.exists() and args.period[4:6] != '03':
        download_fdic(args.prior_period, fdic_prior)

    y9_now = load_y9(args.y9_current)
    y9_prior_rows = load_y9(args.y9_prior) if args.period[4:6] != '03' else []
    validate_records(y9_now, "RSSD9001", "RSSD9999", args.period)
    if y9_prior_rows:
        validate_records(y9_prior_rows, "RSSD9001", "RSSD9999", args.prior_period)
    y9_prev = {as_int(row["RSSD9001"]): row for row in y9_prior_rows}
    banks = load_fdic_json(fdic_current)
    prior_banks = load_fdic_json(fdic_prior) if args.period[4:6] != '03' else []
    validate_records(banks, "CERT", "REPDTE", args.period)
    if prior_banks:
        validate_records(prior_banks, "CERT", "REPDTE", args.prior_period)
    banks_prev = {as_int(row.get("CERT")): row for row in prior_banks}

    bhc_by_rssd = {as_int(row["RSSD9001"]): row for row in y9_now}
    holder_counts = Counter(
        as_int(bank.get("RSSDHCR")) for bank in banks
        if as_int(bank.get("RSSDHCR")) in bhc_by_rssd
    )
    bhc_candidates = [row for row in y9_now if as_int(row["RSSD9001"]) in holder_counts]
    bhc_candidates.sort(key=lambda row: as_int(row["BHCK2170"]) or -1, reverse=True)
    selected_bhcs = y9_now if args.all_bhcs else bhc_candidates[: args.bhcs]
    selected_ids = {as_int(row["RSSD9001"]) for row in selected_bhcs}

    holder_names = {}
    for bank in banks:
        holder = as_int(bank.get("RSSDHCR"))
        name = bank.get("NAMEHCR")
        if holder and name:
            holder_names.setdefault(holder, name)

    standalone = [
        bank for bank in banks
        if (
            not as_int(bank.get("RSSDHCR"))
            or as_int(bank.get("RSSDHCR")) == as_int(bank.get("RSSDID"))
        )
        and (args.all_bank_candidates or all(as_int(bank.get(field)) is not None for field in ("ASSET", "LNLSNET", "DEP", "EQ", "NETINC", "NETINCQ")))
    ]
    standalone.sort(key=lambda row: as_int(row.get("ASSET")) or -1, reverse=True)
    standalone = standalone if args.all_bank_candidates else standalone[: args.standalone_banks]

    institutions = []
    measures = []
    ownership = []
    provenance = []

    def add_measure(entity_key, source, measure, value, source_variable, kind):
        measures.append({
            "entity_key": entity_key, "report_date": args.period,
            "measure": measure, "value_usd_thousands": value,
            "measurement_type": kind, "source": source,
            "source_variable": source_variable,
        })

    for row in selected_bhcs:
        rssd = as_int(row["RSSD9001"])
        key = f"BHC_RSSD_{rssd}"
        institutions.append({
            "entity_key": key, "entity_level": "consolidated_BHC",
            "name": holder_names.get(rssd, f"BHC RSSD {rssd}"),
            "rssd_id": rssd, "fdic_cert": "", "state": "",
            "report_date": args.period, "included_in_analysis": True,
        })
        prev = y9_prev.get(rssd, {})
        add_measure(key, "FR_Y9C", "total_assets", as_int(row["BHCK2170"]), "BHCK2170", "stock")
        add_measure(key, "FR_Y9C", "total_loans", as_int(row["BHCK2122"]), "BHCK2122", "stock")
        add_measure(key, "FR_Y9C", "total_deposits", deposits_y9(row), "BHDM6631+BHDM6636+BHFN6631+BHFN6636", "stock")
        add_measure(key, "FR_Y9C", "total_equity", as_int(row["BHCK3210"]), "BHCK3210", "stock")
        add_measure(key, "FR_Y9C", "net_income_ytd", as_int(row["BHCK4340"]), "BHCK4340", "YTD_flow")
        add_measure(key, "FR_Y9C", "net_income_quarter", quarter_from_ytd(args.period, row["BHCK4340"], prev.get("BHCK4340")), "BHCK4340-current minus BHCK4340-prior", "quarter_flow")

    for bank in standalone:
        rssd, cert = as_int(bank.get("RSSDID")), as_int(bank.get("CERT"))
        key = f"BANK_CERT_{cert}"
        institutions.append({
            "entity_key": key, "entity_level": "standalone_candidate_bank",
            "name": bank.get("NAME"), "rssd_id": rssd, "fdic_cert": cert,
            "state": bank.get("STALP", ""), "report_date": args.period,
            "included_in_analysis": True,
        })
        for measure, field, kind in [
            ("total_assets", "ASSET", "stock"), ("loans_net_allowances", "LNLSNET", "stock"),
            ("total_deposits", "DEP", "stock"), ("total_equity", "EQ", "stock"),
            ("net_income_ytd", "NETINC", "YTD_flow"), ("net_income_quarter", "NETINCQ", "quarter_flow"),
        ]:
            add_measure(key, "FDIC_CALL", measure, as_int(bank.get(field)), field, kind)

    for bank in banks:
        holder = as_int(bank.get("RSSDHCR"))
        if holder in selected_ids:
            ownership.append({
                "report_date": args.period, "bank_rssd_id": as_int(bank.get("RSSDID")),
                "bank_fdic_cert": as_int(bank.get("CERT")), "bank_name": bank.get("NAME"),
                "top_holder_rssd_id": holder, "top_holder_name": bank.get("NAMEHCR") or holder_names.get(holder, ""),
                "match_basis": "FDIC RSSDHCR at the same quarter end",
                "included_as_separate_entity": False,
            })

    validations = []
    def check(name, passed, detail):
        validations.append({"check": name, "status": "PASS" if passed else "FAIL", "detail": detail})

    check("raw_dates_unique_and_complete", True, "Both raw sources checked before dictionary joins; FDIC count equals meta.total")
    check("core_values_complete", all(r["value_usd_thousands"] is not None for r in measures), "Every selected core measure must be populated")

    keys = [(row["entity_key"], row["report_date"]) for row in institutions]
    check("unique_entity_period", len(keys) == len(set(keys)), f"{len(keys)} output entity-period rows")
    check("bhc_prior_period_available", args.period[4:6] == '03' or all(as_int(row["RSSD9001"]) in y9_prev for row in selected_bhcs), "Required for non-Q1 YTD-to-quarter conversion")
    check("no_bhc_subsidiary_double_count", not any(as_int(bank.get("RSSDHCR")) in selected_ids for bank in standalone), "Selected standalone banks are not subsidiaries of selected BHCs")
    check("period_aware_ownership", all(row["report_date"] == args.period for row in ownership), f"{len(ownership)} matched bank subsidiaries use same-period RSSDHCR")
    stocks = {(r["entity_key"], r["measure"]): r["value_usd_thousands"] for r in measures}
    sane = True
    for inst in institutions:
        key = inst["entity_key"]
        asset = stocks.get((key, "total_assets"))
        for measure in ("total_loans", "loans_net_allowances", "total_deposits", "total_equity"):
            value = stocks.get((key, measure))
            sane &= value is None or (value >= 0 and asset is not None and value <= asset * 1.05)
    check("balance_sheet_sanity", bool(sane), "Loans, deposits and equity are nonnegative and no more than 105% of assets")
    fdic_flow_matches = []
    for bank in standalone:
        prior = banks_prev.get(as_int(bank.get("CERT")))
        if (prior or args.period[4:6] == '03') and as_int(bank.get("NETINCQ")) is not None:
            diff = quarter_from_ytd(args.period, bank.get("NETINC"), (prior or {}).get("NETINC"))
            fdic_flow_matches.append(diff == as_int(bank.get("NETINCQ")))
    check("fdic_quarter_flow_crosscheck", len(fdic_flow_matches) == len(standalone) and all(fdic_flow_matches), f"{sum(fdic_flow_matches)}/{len(standalone)} candidate banks: NETINCQ equals YTD difference")

    provenance.extend([
        {"source": "FR_Y9C", "report_date": args.period, "official_url": Y9_URL.format(period=args.period), "local_file": str(args.y9_current), "sha256": sha256(args.y9_current), "retrieved_at_utc": datetime.now(timezone.utc).isoformat()},
        {"source": "FR_Y9C", "report_date": args.prior_period, "official_url": Y9_URL.format(period=args.prior_period), "local_file": str(args.y9_prior), "sha256": optional_prior_hash(args.y9_prior, args.period), "retrieved_at_utc": datetime.now(timezone.utc).isoformat()},
        {"source": "FDIC_CALL", "report_date": args.period, "official_url": FDIC_API, "local_file": str(fdic_current), "sha256": sha256(fdic_current), "retrieved_at_utc": datetime.now(timezone.utc).isoformat()},
        {"source": "FDIC_CALL", "report_date": args.prior_period, "official_url": FDIC_API, "local_file": str(fdic_prior), "sha256": optional_prior_hash(fdic_prior, args.period), "retrieved_at_utc": datetime.now(timezone.utc).isoformat()},
    ])
    if args.period[4:6] == '03':
        provenance = [r for r in provenance if r['report_date'] == args.period]
    for record in provenance:
        record["processed_at_utc"] = record.pop("retrieved_at_utc")
        record["request_parameters"] = json.dumps(json.loads(Path(record["local_file"]).read_text(encoding="utf-8"))["meta"].get("parameters", {}), sort_keys=True) if record["source"] == "FDIC_CALL" else ""

    # Keep bank-subsidiary deposit aggregates distinct from consolidated BHC totals.
    deposit_rows = []
    for inst in institutions:
        members = [b for b in banks if as_int(b.get("RSSDHCR")) == inst["rssd_id"]] if inst["entity_level"] == "consolidated_BHC" else [b for b in standalone if as_int(b["CERT"]) == inst["fdic_cert"]]
        result = {"entity_key": inst["entity_key"], "report_date": args.period, "bank_count": len(members), "perimeter": "FDIC reporting banks only; not consolidated BHC"}
        for field in ("DEP", "DEPDOM", "DEPFOR", "DEPIDOM", "DEPNIDOM"):
            values = [as_int(b.get(field)) for b in members]
            result[field] = sum(values) if values and all(v is not None for v in values) else None
            result[field + "_missing_banks"] = sum(v is None for v in values)
        consolidated = next((m["value_usd_thousands"] for m in measures if m["entity_key"] == inst["entity_key"] and m["measure"] == "total_deposits"), None)
        result["core_reported_deposits"] = consolidated
        result["bank_sum_minus_core"] = result["DEP"] - consolidated if result["DEP"] is not None and consolidated is not None else None
        deposit_rows.append(result)
    deposit_columns = ["entity_key", "report_date", "bank_count", "perimeter", "core_reported_deposits", "bank_sum_minus_core"] + [v for f in ("DEP", "DEPDOM", "DEPFOR", "DEPIDOM", "DEPNIDOM") for v in (f, f + "_missing_banks")]
    check("deposit_domestic_components_reconcile", all(r["DEPDOM"] is not None and r["DEPIDOM"] is not None and r["DEPNIDOM"] is not None and abs(r["DEPDOM"] - r["DEPIDOM"] - r["DEPNIDOM"]) <= max(1, r["bank_count"]) for r in deposit_rows), "Domestic deposits equal interest-bearing plus noninterest-bearing; missing categories fail")
    check("all_validation_checks_pass", all(row["status"] == "PASS" for row in validations), "Summary of preceding checks")

    tables = {
        "institutions": (institutions, ["entity_key", "entity_level", "name", "rssd_id", "fdic_cert", "state", "report_date", "included_in_analysis"]),
        "measures": (measures, ["entity_key", "report_date", "measure", "value_usd_thousands", "measurement_type", "source", "source_variable"]),
        "ownership": (ownership, ["report_date", "bank_rssd_id", "bank_fdic_cert", "bank_name", "top_holder_rssd_id", "top_holder_name", "match_basis", "included_as_separate_entity"]),
        "validation": (validations, ["check", "status", "detail"]),
        "provenance": (provenance, ["source", "report_date", "official_url", "local_file", "sha256", "processed_at_utc", "request_parameters"]),
        "deposits": (deposit_rows, deposit_columns),
    }
    coverage = []
    bank_ids = {as_int(b['CERT']) for b in standalone}
    for bank in banks:
        holder = as_int(bank.get('RSSDHCR'))
        coverage.append({'bank_cert': as_int(bank['CERT']), 'bank_rssd': as_int(bank.get('RSSDID')), 'report_date': args.period, 'holder_rssd': holder, 'status': 'SUBSIDIARY_REPRESENTED_BY_Y9C' if holder in selected_ids else 'STANDALONE_CANDIDATE_REVIEW' if as_int(bank['CERT']) in bank_ids else 'HOLDER_WITHOUT_SELECTED_Y9C_OR_OUTSIDE_SAMPLE'})
    tables['bank_coverage'] = (coverage, ['bank_cert','bank_rssd','report_date','holder_rssd','status'])
    db_path = args.output / "bpi_mvp.duckdb"
    if db_path.exists():
        db_path.unlink()
    con = duckdb.connect(str(db_path))
    for name, (rows, columns) in tables.items():
        csv_path = args.output / f"{name}.csv"
        write_csv(csv_path, rows, columns)
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM read_csv_auto(?, header=true)", [str(csv_path)])
        con.execute(f"COPY {name} TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(args.output / f"{name}.parquet")])
    con.execute("CREATE TABLE financials_wide AS PIVOT measures ON measure USING first(value_usd_thousands) GROUP BY entity_key, report_date")
    con.execute("COPY financials_wide TO ? (HEADER, DELIMITER ',')", [str(args.output / "financials_wide.csv")])
    con.execute("COPY financials_wide TO ? (FORMAT PARQUET)", [str(args.output / "financials_wide.parquet")])
    con.close()

    summary = {
        "report_date": args.period, "bhcs": len(selected_bhcs),
        "standalone_banks": len(standalone), "ownership_links": len(ownership),
        "validation_pass": all(row["status"] == "PASS" for row in validations),
        "release_status": "REVIEW_REQUIRED",
        "release_reason": "Standalone candidates require independent ownership verification; loan definitions remain source-specific; merger adjustment pending",
        "output": str(args.output),
    }
    (args.output / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (args.output / "REVIEW_REQUIRED.txt").write_text(summary["release_reason"] + "\nThese files are diagnostic research drafts, not approved publication outputs.\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    result = main()
    raise SystemExit(0 if result["validation_pass"] else 2)
