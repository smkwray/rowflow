from __future__ import annotations

import argparse
from pathlib import Path

from rowflow.config import config_dir_from_root, validate_config_dir
from rowflow.contracts import copy_sibling_outputs, validate_sibling_sources
from rowflow.io import download_text
from rowflow.manifests import write_output_manifest
from rowflow.panels import (
    build_rowflow_panel,
    build_tic_row_panel,
    build_z1_row_panel,
    build_z1_row_panel_from_fred_levels,
    combine_tic_row_panels,
    download_z1_fred_transactions,
)
from rowflow.reports import write_rowflow_report
from rowflow.validation import has_errors, print_messages, validate_rowflow_package


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

    p = sub.add_parser("build-z1-row-panel-from-fred-levels", help="Build quarterly Z.1 ROW comparison panel from local FRED level JSONs.")
    p.add_argument("--official-level-json", required=True, help="FRED JSON observations for BOGZ1FL263061130Q.")
    p.add_argument("--private-level-json", required=True, help="FRED JSON observations for BOGZ1FL263061145Q.")
    p.add_argument("--output", required=True, help="Output CSV path.")

    p = sub.add_parser("build-rowflow-panel", help="Merge TIC, Z.1, TDC, and diagnostic sidecars.")
    p.add_argument("--tic-panel", required=True, help="Built TIC row panel.")
    p.add_argument("--z1-panel", default=None, help="Built Z.1 row panel.")
    p.add_argument("--diagnostics", default=None, help="Monthly diagnostics CSV.")
    p.add_argument("--tdc-context", default=None, help="Quarterly TDC context CSV.")
    p.add_argument("--output", required=True, help="Output rowflow panel CSV.")

    p = sub.add_parser("write-rowflow-report", help="Write accounting report and figure set.")
    p.add_argument("--panel", required=True, help="Built rowflow panel CSV.")
    p.add_argument("--z1-panel", default=None, help="Built Z.1 row panel CSV.")
    p.add_argument("--output-md", required=True, help="Output markdown report path.")
    p.add_argument("--figure-dir", required=True, help="Output figure directory.")

    p = sub.add_parser("write-output-manifest", help="Write output manifest with hashes.")
    p.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    p.add_argument("--output", required=True, help="Output JSON manifest path.")

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
                tdc_context_path=Path(args.tdc_context) if args.tdc_context else None,
                output_path=Path(args.output),
            )
            print(f"Wrote {len(panel):,} row(s) to {args.output}")
            return 0

        if args.command == "write-rowflow-report":
            result = write_rowflow_report(
                panel_path=Path(args.panel),
                z1_panel_path=Path(args.z1_panel) if args.z1_panel else None,
                output_md=Path(args.output_md),
                figure_dir=Path(args.figure_dir),
            )
            print(f"Wrote report to {result['report']}")
            for figure in result["figures"]:
                print(f"Wrote figure {figure}")
            return 0

        if args.command == "write-output-manifest":
            manifest = write_output_manifest(_root(args.root), Path(args.output))
            print(f"Wrote manifest with {len(manifest['files'])} file(s) to {args.output}")
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
