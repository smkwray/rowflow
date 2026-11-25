# rowflow command reference

The `make` targets in the README chain these commands. Each command also runs on its own against any local CSV or text file that matches the expected schema. `rowflow <command> --help` lists every option.

## Monthly TIC and Z.1 panel

```bash
rowflow validate-config
rowflow download-z1-fred-transactions --output data/raw/z1/z1_row_official_private_transactions.csv
rowflow build-tic-row-panel --input data/raw/tic/tressect.txt --output data/derived/tic_row_monthly_legacy.csv
rowflow build-tic-row-panel --input data/imported/tic/slt_table3.txt --output data/derived/tic_row_monthly_slt.csv
rowflow combine-tic-row-panels \
  --input data/derived/tic_row_monthly_legacy.csv \
  --input data/derived/tic_row_monthly_slt.csv \
  --output data/derived/tic_row_monthly.csv
rowflow build-z1-row-panel \
  --input data/raw/z1/z1_row_official_private_transactions.csv \
  --transactions-are-quarterly \
  --output data/derived/z1_row_quarterly.csv
rowflow build-rowflow-panel \
  --tic-panel data/derived/tic_row_monthly.csv \
  --z1-panel data/derived/z1_row_quarterly.csv \
  --output data/derived/rowflow_panel.csv
rowflow write-rowflow-report \
  --panel data/derived/rowflow_panel.csv \
  --z1-panel data/derived/z1_row_quarterly.csv \
  --output-md output/reports/rowflow_accounting_report.md \
  --figure-dir output/figures \
  --table-dir output/tables
```

`build-rowflow-panel` also accepts optional sibling inputs: `--diagnostics`, `--issuance-diagnostics`, `--debt-denominators`, `--fred-diagnostics` and `--tdc-context`. `make real-package` shows which sibling file feeds each one.

## Episode totals and determinant regressions

`make real-determinants` runs `write-source-regime-ledger`, `write-episode-absorption`, `build-determinant-panel`, `write-determinant-tables`, `write-compact-determinant-table`, `write-compact-determinant-markdown` and `write-determinant-report` in that order. The regressions are monthly ordinary least squares with Newey-West heteroskedasticity- and autocorrelation-consistent (HAC) standard errors at lag 3, as set in `config/determinant_specs.yml`.

## Quarterly rest-of-world Z.1 account

These commands download a dated Federal Reserve Z.1 release archive, fetch vintage-matched ALFRED (archival FRED) series, build the quarterly rest-of-world sources-and-uses account, and compare two vintages:

```bash
rowflow download-z1-archive --vintage 2026-03-19 --table fu133 --output data/raw/z1/2026-03-19
rowflow download-z1-sidecars --vintage 2026-03-19 --spec config/row_ledger.yml --output data/raw/z1/2026-03-19/alfred
rowflow build-z1-ledger --input data/raw/z1/2026-03-19 --spec config/row_ledger.yml --output output/z1_ledger_2026-03-19
rowflow write-z1-revision-bridge --frozen output/z1_ledger_2026-03-19/quarterly.csv --revised output/z1_ledger_2026-06-11/quarterly.csv --output output/z1_revision_bridge.csv
```

`download-z1-archive` writes to a new directory and never overwrites an existing vintage. `build-z1-ledger` writes the quarterly account table (`quarterly.csv`), the detailed series table (`ledger.csv`), accounting cross-checks and `summary.json` into its `--output` directory. See [row_ledger.md](row_ledger.md) for the account structure.
