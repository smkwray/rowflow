# rowflow

`rowflow` builds descriptive panels and tables that split rest-of-world US Treasury absorption into foreign official institutions, foreign private holders, and international and regional organizations. It combines monthly Treasury International Capital (TIC) data, quarterly Financial Accounts of the United States (Z.1) data, and optional Treasury issuance and domestic liquidity panels, writing merged panels, episode totals, OLS determinant tables, SVG charts, and Markdown reports.

## Data

Standalone runs download public data directly, with no API keys required:

- Treasury International Capital (TIC): pre-2023 monthly net foreign purchases of long-term US Treasury bonds and notes (`tressect.txt`) and expanded SLT Table 3 monthly foreign Treasury holdings and net flows from February 2023 onward (`slt_table3.txt`).
- Federal Reserve Financial Accounts (Z.1) via public FRED CSV downloads: quarterly unadjusted foreign official and foreign private Treasury transactions and holdings.
- FRED public CSV download of the nominal broad US dollar index.
- Dated Federal Reserve Z.1 release archives and vintage-matched ALFRED series when running the quarterly rest-of-world account commands.

Full real-data `make` builds also read local CSV outputs from sibling checkouts (`buycurve`, `liqsub`, `tdcest`, and optionally `qrawatch`, `tdcladder`, `bankcap`, `tdcpass`, `tdcatlas`) located under `..`, or at paths set by `<PROJECT>_ROOT` environment variables (for example `BUYCURVE_ROOT`, `LIQSUB_ROOT`, `TDCEST_ROOT`, `QRAWATCH_ROOT`). In `Makefile`, the default SLT Table 3 path points to a local `buycurve` checkout and can be overridden with `SLT=<file>`.

## Install

Requires Python 3.11 or later. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

## Usage

Run the fixture-backed pipeline with no network access or sibling repositories:

```bash
make smoke-fixtures
```

Run the full real-data build when sibling repositories are present next to `rowflow`:

```bash
make real-package
make real-determinants
```

Pass `BUILD_ROOT=<dir>` to write downloaded inputs, derived panels, and outputs under `<dir>` instead of the repository root, and `SLT=<file>` to point at a local copy of TIC SLT Table 3. `PYTHON`, `RUFF`, and `ROWFLOW` override the executables used by `make`.

Individual CLI commands work on any local CSV or text files matching the expected schemas:

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

For episode totals and monthly OLS determinant regressions (with lag-3 Newey-West HAC standard errors under `config/determinant_specs.yml`), run `make real-determinants` or see `rowflow --help` for the individual table and report commands.

To download a dated Federal Reserve Z.1 archive, fetch vintage-matched ALFRED series, build the quarterly rest-of-world sources-and-uses account, and compare two vintages:

```bash
rowflow download-z1-archive --vintage 2026-03-19 --table fu133 --output data/raw/z1/2026-03-19
rowflow download-z1-sidecars --vintage 2026-03-19 --spec config/row_ledger.yml --output data/raw/z1/2026-03-19/alfred
rowflow build-z1-ledger --input data/raw/z1/2026-03-19 --spec config/row_ledger.yml --output output/z1_ledger_2026-03-19
rowflow write-z1-revision-bridge --frozen output/z1_ledger_2026-03-19/quarterly.csv --revised output/z1_ledger_2026-06-11/quarterly.csv --output output/z1_revision_bridge.csv
```

## Output

Generated files live under `data/derived/` and `output/` (both gitignored) and express dollar flows and levels in USD millions:

| Path | Description |
| --- | --- |
| `data/derived/rowflow_panel.csv` | Monthly panel combining TIC flows and quarterly Z.1 transactions |
| `output/tables/` | Episode totals, source-period summaries, and monthly OLS determinant tables |
| `output/figures/` | SVG charts of official vs. private flows, official share, and stocks vs. flows |
| `output/reports/` | Markdown summaries of accounting comparisons and determinant regressions |
| `output/manifests/rowflow_manifest.json` | SHA-256 hashes of generated output files |

`build-z1-ledger` writes the quarterly rest-of-world account table (`quarterly.csv`), detailed series table (`ledger.csv`), accounting cross-checks, and `summary.json` into its `--output` directory.

## Limits

- Results are descriptive accounting summaries and conditional associations; the package does not estimate causal demand curves or causal domestic liquidity effects.
- Pre-2023 legacy TIC data (`tressect.txt`) cover long-term Treasury bonds and notes only, while expanded SLT Table 3 from February 2023 onward covers total Treasury securities. The two source periods carry explicit labels and are not pooled in determinant regressions.
- TIC and Z.1 differ in frequency, coverage, and revision timing, and neither identifies ultimate beneficial owners beyond reported custodial and counterparty definitions.
- In `build-z1-ledger`, transaction-accounting checks run across the configured Z.1 series, while independent stock checks remain unavailable where dated level, revaluation, or other-volume series are unestablished (for example, gold and SDR holdings).

See [source notes](docs/source_notes.md) and the [rest-of-world Z.1 account notes](docs/row_ledger.md) for series details.

## Tests

The test suite runs against small CSV fixtures under `tests/fixtures/` with no network calls:

```bash
python -B -m pytest -q
ruff check src tests
rowflow validate-config
```

## License

MIT. See [LICENSE](LICENSE).
