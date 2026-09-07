from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from rowflow.config import config_dir_from_root, validate_config_dir
from rowflow.contracts import copy_sibling_outputs, validate_sibling_sources
from rowflow.determinant_report import write_determinant_report
from rowflow.determinants import build_determinant_panel
from rowflow.episodes import write_episode_absorption
from rowflow.io import download_text
from rowflow.ledger import write_source_regime_ledger
from rowflow.manifests import write_output_manifest
from rowflow.panels import (
    build_rowflow_panel,
    build_tic_row_panel,
    build_z1_row_panel,
    build_z1_row_panel_from_fred_levels,
    combine_tic_row_panels,
    download_z1_fred_transactions,
)
from rowflow.ratewall_contracts import write_ratewall_foreign_route_support_contract
from rowflow.regressions import (
    write_compact_determinant_markdown,
    write_compact_determinant_table,
    write_determinant_tables,
)
from rowflow.reports import write_rowflow_report
from rowflow.validation import has_errors, print_messages, validate_rowflow_package
from rowflow.z1_archive import acquire_alfred_series, acquire_archive
from rowflow.z1_ledger import build_ledger, write_revision_bridge


def _root(value: str | None) -> Path:
    return Path(value or ".").expanduser().resolve()


def _config_dir(args: argparse.Namespace) -> Path:
    if getattr(args, "config_dir", None):
        return Path(args.config_dir).expanduser().resolve()
    return config_dir_from_root(_root(getattr(args, "root", None))).resolve()


def _add_root_config(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--config-dir", default=None, help="Config directory. Defaults to ROOT/config.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rowflow")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate-config", help="Validate public config files.")
    _add_root_config(p)

    p = sub.add_parser("validate-sibling-sources", help="Check configured sibling artifacts.")
    _add_root_config(p)
    p.add_argument("--sibling-root", default=None, help="Directory containing sibling repo folders.")
    p.add_argument("--strict", action="store_true", help="Fail when required sibling artifacts are missing.")

    p = sub.add_parser("copy-sibling-outputs", help="Copy configured sibling outputs into ignored data/imported folders.")
    _add_root_config(p)
    p.add_argument("--sibling-root", default=None, help="Directory containing sibling repo folders.")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing imported copies.")
    p.add_argument("--strict", action="store_true", help="Fail when required sibling artifacts are missing.")
    p.add_argument("--manifest", default=None, help="CSV copy manifest path.")

    p = sub.add_parser("build-tic-row-panel", help="Build monthly TIC official/private ROW Treasury panel.")
    p.add_argument("--input", required=True, help="Input TIC CSV/TXT file.")
    p.add_argument("--output", required=True, help="Output CSV path.")

    p = sub.add_parser("combine-tic-row-panels", help="Combine monthly TIC panels, preferring later inputs on overlap.")
    p.add_argument("--input", action="append", required=True, help="Input built TIC panel. May be repeated.")
    p.add_argument("--output", required=True, help="Output CSV path.")

    p = sub.add_parser("download-text-source", help="Download a public text/CSV source to a local ignored path.")
    p.add_argument("--url", required=True, help="Source URL.")
    p.add_argument("--output", required=True, help="Output path.")

    p = sub.add_parser("build-z1-row-panel", help="Build quarterly Z.1 official/private ROW comparison panel.")
    p.add_argument("--input", required=True, help="Input Z.1 CSV file.")
    p.add_argument("--output", required=True, help="Output CSV path.")
    p.add_argument("--transactions-are-quarterly", action="store_true", help="Do not divide transaction input values by four.")

    p = sub.add_parser("download-z1-fred-transactions", help="Download FRED Z.1 official/private transaction graph CSVs.")
    p.add_argument("--output", required=True, help="Output merged CSV path.")

    p = sub.add_parser("download-z1-archive", help="Retain selected tables and dictionaries from a dated Fed archive.")
    p.add_argument("--vintage", required=True, help="Final release date YYYY-MM-DD.")
    p.add_argument("--table", action="append", required=True, help="Exact archive table stem; repeat as needed.")
    p.add_argument("--output", required=True, help="New source directory; existing vintages are never overwritten.")

    p = sub.add_parser("download-z1-sidecars", help="Acquire configured ALFRED series at one exact vintage.")
    p.add_argument("--vintage", required=True)
    p.add_argument("--spec", default="config/row_ledger.yml")
    p.add_argument("--output", required=True)

    p = sub.add_parser("build-z1-ledger", help="Write a dated ROW ledger, source receipts and certification diagnostics.")
    p.add_argument("--input", required=True, help="Dated source directory with receipt.json.")
    p.add_argument("--spec", default="config/row_ledger.yml")
    p.add_argument("--output", required=True, help="Diagnostic output directory.")

    p = sub.add_parser("write-z1-revision-bridge", help="Compare two dated ledger exports by stable series ID.")
    p.add_argument("--frozen", required=True)
    p.add_argument("--revised", required=True)
    p.add_argument("--output", required=True)

    p = sub.add_parser("build-z1-row-panel-from-fred-levels", help="Build quarterly Z.1 ROW comparison panel from local FRED level JSONs.")
    p.add_argument("--official-level-json", required=True, help="FRED JSON observations for BOGZ1FL263061130Q.")
    p.add_argument("--private-level-json", required=True, help="FRED JSON observations for BOGZ1FL263061145Q.")
    p.add_argument("--output", required=True, help="Output CSV path.")

    p = sub.add_parser("build-rowflow-panel", help="Merge TIC, Z.1, TDC, and diagnostic sidecars.")
    p.add_argument("--tic-panel", required=True, help="Built TIC row panel.")
    p.add_argument("--z1-panel", default=None, help="Built Z.1 row panel.")
    p.add_argument("--diagnostics", default=None, help="Monthly diagnostics CSV.")
    p.add_argument("--issuance-diagnostics", default=None, help="Monthly issuance diagnostics CSV.")
    p.add_argument("--debt-denominators", default=None, help="Monthly debt stock/net issuance denominator CSV.")
    p.add_argument(
        "--fred-diagnostics",
        action="append",
        default=None,
        help="Monthly or higher-frequency FRED diagnostics CSV. May be repeated.",
    )
    p.add_argument("--tdc-context", default=None, help="Quarterly TDC context CSV.")
    p.add_argument("--output", required=True, help="Output rowflow panel CSV.")

    p = sub.add_parser("write-source-regime-ledger", help="Write source-regime ledger CSV and optional Markdown.")
    p.add_argument("--tic-panel", required=True, help="Built TIC row panel.")
    p.add_argument("--z1-panel", default=None, help="Built Z.1 row panel.")
    p.add_argument("--output-csv", required=True, help="Output source-regime ledger CSV.")
    p.add_argument("--output-md", default=None, help="Optional output Markdown ledger.")

    p = sub.add_parser("write-episode-absorption", help="Write episode-level official/private absorption accounting.")
    p.add_argument("--panel", required=True, help="Built rowflow panel CSV.")
    p.add_argument("--z1-panel", required=True, help="Built Z.1 row panel CSV.")
    p.add_argument("--episodes", required=True, help="Episode registry YAML.")
    p.add_argument("--output", required=True, help="Output episode absorption CSV.")

    p = sub.add_parser("build-determinant-panel", help="Build monthly determinant panel with lags and standardized regressors.")
    p.add_argument("--panel", required=True, help="Built rowflow panel CSV.")
    p.add_argument("--spec", required=True, help="Determinant spec YAML.")
    p.add_argument("--output", required=True, help="Output determinant panel CSV.")
    p.add_argument(
        "--missingness-output",
        default="output/tables/determinant_panel_missingness.csv",
        help="Output missingness audit CSV.",
    )

    p = sub.add_parser("write-determinant-tables", help="Write first-pass descriptive determinant tables.")
    p.add_argument("--panel", required=True, help="Built determinant panel CSV.")
    p.add_argument("--spec", required=True, help="Determinant spec YAML.")
    p.add_argument("--output", required=True, help="Output determinant table CSV.")

    p = sub.add_parser("write-compact-determinant-table", help="Write presentation-oriented compact determinant table.")
    p.add_argument("--determinants", required=True, help="Full determinant table CSV.")
    p.add_argument("--output", required=True, help="Output compact determinant table CSV.")

    p = sub.add_parser("write-compact-determinant-markdown", help="Write Markdown companion for compact determinant table.")
    p.add_argument("--compact", required=True, help="Compact determinant table CSV.")
    p.add_argument("--output-md", required=True, help="Output Markdown summary.")
    p.add_argument("--max-rows", type=int, default=12, help="Maximum compact rows to show.")

    p = sub.add_parser("write-determinant-report", help="Write determinant summary report.")
    p.add_argument("--panel", required=True, help="Built determinant panel CSV.")
    p.add_argument("--ledger", required=True, help="Source-regime ledger CSV.")
    p.add_argument("--episodes", required=True, help="Episode absorption CSV.")
    p.add_argument("--determinants", required=True, help="Determinant table CSV.")
    p.add_argument("--output-md", required=True, help="Output Markdown report.")

    p = sub.add_parser("write-rowflow-report", help="Write accounting report and figure set.")
    p.add_argument("--panel", required=True, help="Built rowflow panel CSV.")
    p.add_argument("--z1-panel", default=None, help="Built Z.1 row panel CSV.")
    p.add_argument("--output-md", required=True, help="Output markdown report path.")
    p.add_argument("--figure-dir", required=True, help="Output figure directory.")
    p.add_argument("--table-dir", default=None, help="Output results table directory. Defaults to OUTPUT_PARENT/tables.")

    p = sub.add_parser("write-output-manifest", help="Write output manifest with hashes.")
    p.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    p.add_argument("--output", required=True, help="Output JSON manifest path.")

    p = sub.add_parser("write-ratewall-foreign-route-support", help="Write RateWall foreign-route support contract.")
    p.add_argument("--panel", default="data/derived/rowflow_panel.csv", help="Built rowflow panel CSV.")
    p.add_argument("--z1-panel", default="data/derived/z1_row_quarterly_real.csv", help="Optional Z.1 ROW panel CSV.")
    p.add_argument("--output", default="output/contracts/rowflow_ratewall_foreign_route_support.csv", help="Output support contract CSV.")

    p = sub.add_parser("validate-rowflow-package", help="Validate config, panel, report, manifest, and claim boundary.")
    _add_root_config(p)
    p.add_argument("--panel", default="data/derived/rowflow_panel.csv", help="Rowflow panel path.")
    p.add_argument("--report", default="output/reports/rowflow_accounting_report.md", help="Markdown report path.")
    p.add_argument("--manifest", default="output/manifests/rowflow_manifest.json", help="Output manifest path.")
    p.add_argument("--strict", action="store_true", help="Fail on missing package artifacts.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "validate-config":
            messages = validate_config_dir(_config_dir(args))
            print_messages(messages)
            return 1 if has_errors(messages) else 0

        if args.command == "validate-sibling-sources":
            sibling_root = Path(args.sibling_root).expanduser().resolve() if args.sibling_root else None
            messages = validate_sibling_sources(_config_dir(args), sibling_root, strict=args.strict)
            print_messages(messages)
            return 1 if has_errors(messages) else 0

        if args.command == "copy-sibling-outputs":
            sibling_root = Path(args.sibling_root).expanduser().resolve() if args.sibling_root else None
            manifest = Path(args.manifest).expanduser().resolve() if args.manifest else None
            rows = copy_sibling_outputs(
                _config_dir(args),
                project_root=_root(args.root),
                sibling_root=sibling_root,
                overwrite=args.overwrite,
                strict=args.strict,
                manifest_path=manifest,
            )
            print_messages([{ "level": row["level"], "message": f"{row['status']}: {row['project']}:{row['artifact']}"} for row in rows])
            return 1 if any(row["level"] == "error" for row in rows) else 0

        if args.command == "build-tic-row-panel":
            panel = build_tic_row_panel(Path(args.input), Path(args.output))
            print(f"Wrote {len(panel):,} row(s) to {args.output}")
            return 0

        if args.command == "combine-tic-row-panels":
            panel = combine_tic_row_panels([Path(value) for value in args.input], Path(args.output))
            print(f"Wrote {len(panel):,} row(s) to {args.output}")
            return 0

        if args.command == "download-text-source":
            output = download_text(args.url, Path(args.output))
            print(f"Wrote {output}")
            return 0

        if args.command == "build-z1-row-panel":
            panel = build_z1_row_panel(
                Path(args.input),
                Path(args.output),
                transactions_are_saar=not args.transactions_are_quarterly,
            )
            print(f"Wrote {len(panel):,} row(s) to {args.output}")
            return 0

        if args.command == "download-z1-fred-transactions":
            panel = download_z1_fred_transactions(Path(args.output))
            print(f"Wrote {len(panel):,} row(s) to {args.output}")
            return 0

        if args.command == "download-z1-archive":
            members = [f"{folder}/{table}.{extension}" for table in args.table
                       for folder, extension in [("csv", "csv"), ("data_dictionary", "txt")]]
            url = f"https://www.federalreserve.gov/releases/z1/{args.vintage.replace('-', '')}/z1_csv_files.zip"
            receipt = acquire_archive(url, args.vintage, members, Path(args.output))
            print(json.dumps(receipt, indent=2))
            return 0

        if args.command == "download-z1-sidecars":
            spec = yaml.safe_load(Path(args.spec).read_text())
            receipt = acquire_alfred_series(args.vintage, spec["alfred_series"], Path(args.output))
            print(json.dumps(receipt, indent=2))
            return 0

        if args.command == "build-z1-ledger":
            summary = build_ledger(Path(args.input), Path(args.spec), Path(args.output))
            print(json.dumps(summary, indent=2))
            return 0 if summary["certified"] else 1

        if args.command == "write-z1-revision-bridge":
            frame = write_revision_bridge(Path(args.frozen), Path(args.revised), Path(args.output))
            print(f"Wrote {len(frame)} revision comparisons to {args.output}")
            return 0

        if args.command == "build-z1-row-panel-from-fred-levels":
            panel = build_z1_row_panel_from_fred_levels(
                official_level_json_path=Path(args.official_level_json),
                private_level_json_path=Path(args.private_level_json),
                output_path=Path(args.output),
            )
            print(f"Wrote {len(panel):,} row(s) to {args.output}")
            return 0

        if args.command == "build-rowflow-panel":
            panel = build_rowflow_panel(
                tic_panel_path=Path(args.tic_panel),
                z1_panel_path=Path(args.z1_panel) if args.z1_panel else None,
                diagnostics_path=Path(args.diagnostics) if args.diagnostics else None,
                issuance_diagnostics_path=Path(args.issuance_diagnostics) if args.issuance_diagnostics else None,
                debt_denominators_path=Path(args.debt_denominators) if args.debt_denominators else None,
                fred_diagnostics_path=[Path(value) for value in args.fred_diagnostics] if args.fred_diagnostics else None,
                tdc_context_path=Path(args.tdc_context) if args.tdc_context else None,
                output_path=Path(args.output),
            )
            print(f"Wrote {len(panel):,} row(s) to {args.output}")
            return 0

        if args.command == "write-source-regime-ledger":
            ledger = write_source_regime_ledger(
                tic_panel_path=Path(args.tic_panel),
                z1_panel_path=Path(args.z1_panel) if args.z1_panel else None,
                output_csv=Path(args.output_csv),
                output_md=Path(args.output_md) if args.output_md else None,
            )
            print(f"Wrote {len(ledger):,} row(s) to {args.output_csv}")
            if args.output_md:
                print(f"Wrote report to {args.output_md}")
            return 0

        if args.command == "write-episode-absorption":
            table = write_episode_absorption(
                panel_path=Path(args.panel),
                z1_panel_path=Path(args.z1_panel),
                episodes_path=Path(args.episodes),
                output_path=Path(args.output),
            )
            print(f"Wrote {len(table):,} row(s) to {args.output}")
            return 0

        if args.command == "build-determinant-panel":
            panel = build_determinant_panel(
                panel_path=Path(args.panel),
                spec_path=Path(args.spec),
                output_path=Path(args.output),
                missingness_output_path=Path(args.missingness_output) if args.missingness_output else None,
            )
            print(f"Wrote {len(panel):,} row(s) to {args.output}")
            return 0

        if args.command == "write-determinant-tables":
            table = write_determinant_tables(
                panel_path=Path(args.panel),
                spec_path=Path(args.spec),
                output_path=Path(args.output),
            )
            print(f"Wrote {len(table):,} row(s) to {args.output}")
            return 0

        if args.command == "write-compact-determinant-table":
            table = write_compact_determinant_table(
                determinants_path=Path(args.determinants),
                output_path=Path(args.output),
            )
            print(f"Wrote {len(table):,} row(s) to {args.output}")
            return 0

        if args.command == "write-compact-determinant-markdown":
            report = write_compact_determinant_markdown(
                compact_path=Path(args.compact),
                output_md=Path(args.output_md),
                max_rows=args.max_rows,
            )
            print(f"Wrote report to {report}")
            return 0

        if args.command == "write-determinant-report":
            report = write_determinant_report(
                panel_path=Path(args.panel),
                ledger_path=Path(args.ledger),
                episodes_path=Path(args.episodes),
                determinants_path=Path(args.determinants),
                output_md=Path(args.output_md),
            )
            print(f"Wrote report to {report}")
            return 0

        if args.command == "write-rowflow-report":
            result = write_rowflow_report(
                panel_path=Path(args.panel),
                z1_panel_path=Path(args.z1_panel) if args.z1_panel else None,
                output_md=Path(args.output_md),
                figure_dir=Path(args.figure_dir),
                table_dir=Path(args.table_dir) if args.table_dir else None,
            )
            print(f"Wrote report to {result['report']}")
            for figure in result["figures"]:
                print(f"Wrote figure {figure}")
            for table in result["tables"]:
                print(f"Wrote table {table}")
            return 0

        if args.command == "write-output-manifest":
            manifest = write_output_manifest(_root(args.root), Path(args.output))
            print(f"Wrote manifest with {len(manifest['files'])} file(s) to {args.output}")
            return 0

        if args.command == "write-ratewall-foreign-route-support":
            z1_path = Path(args.z1_panel) if args.z1_panel else None
            if z1_path is not None and not z1_path.exists():
                z1_path = None
            _, frame = write_ratewall_foreign_route_support_contract(
                rowflow_panel_path=Path(args.panel),
                z1_panel_path=z1_path,
                output_path=Path(args.output),
            )
            print(f"Wrote {len(frame):,} row(s) to {args.output}")
            return 0

        if args.command == "validate-rowflow-package":
            root = _root(args.root)
            messages = validate_rowflow_package(
                root=root,
                config_dir=_config_dir(args),
                panel_path=root / args.panel if not Path(args.panel).is_absolute() else Path(args.panel),
                report_path=root / args.report if not Path(args.report).is_absolute() else Path(args.report),
                manifest_path=root / args.manifest if not Path(args.manifest).is_absolute() else Path(args.manifest),
                strict=args.strict,
            )
            print_messages(messages)
            return 1 if has_errors(messages) else 0

    except Exception as exc:  # noqa: BLE001 - CLI should show a concise failure.
        print(f"[ERROR] {exc}")
        return 1

    parser.error(f"Unhandled command: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
