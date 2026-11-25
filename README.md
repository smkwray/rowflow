# rowflow

`rowflow` builds descriptive panels and tables that split rest-of-world US Treasury absorption into foreign official institutions, foreign private holders, and international and regional organizations. It combines monthly Treasury International Capital (TIC) data, quarterly Financial Accounts of the United States (Z.1) data, and optional Treasury issuance and domestic liquidity panels, writing merged panels, episode totals, ordinary least squares (OLS) determinant tables, SVG charts, and Markdown reports.

## Data

Standalone runs download public data directly, with no API keys required:

- Treasury International Capital (TIC): pre-2023 monthly net foreign purchases of long-term US Treasury bonds and notes (`tressect.txt`), and from February 2023 monthly foreign Treasury holdings and net flows from Table 3 of the TIC SLT report, `U.S. Treasury Securities Held by Foreign Residents` (`slt_table3.txt`).
- Federal Reserve Financial Accounts (Z.1) via public CSV downloads from FRED (Federal Reserve Economic Data, St. Louis Fed): quarterly unadjusted foreign official and foreign private Treasury transactions and holdings.
- The nominal broad US dollar index, also from FRED.
- Dated Federal Reserve Z.1 release archives and vintage-matched ALFRED (archival FRED) series, for the quarterly rest-of-world account commands.

Full real-data `make` builds also read CSV outputs from sibling checkouts next to `rowflow` (under `..`), or at paths set by `<PROJECT>_ROOT` environment variables such as `BUYCURVE_ROOT` or `TDCEST_ROOT`. They require [buycurve](https://github.com/smkwray/buycurve), [liqsub](https://github.com/smkwray/liqsub) and [tdcest](https://github.com/smkwray/tdcest), which supplies the Treasury Deposit Component (TDC), the part of the change in deposits at US banks and credit unions that comes from Treasury payments and trades in Treasury securities. [qrawatch](https://github.com/smkwray/qrawatch), [tdcladder](https://github.com/smkwray/tdcladder), [bankcap](https://github.com/smkwray/bankcap), [tdcpass](https://github.com/smkwray/tdcpass) and [tdcatlas](https://github.com/smkwray/tdcatlas) are optional. The default SLT Table 3 path in `Makefile` points into a local `buycurve` checkout; override it with `SLT=<file>`. The fixture run below needs none of them.

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

Run a real-data build when the sibling repositories are present:

```bash
make real-package        # panel, accounting report and charts
make real-determinants   # real-package, then episode totals and determinant regressions
```

Pass `BUILD_ROOT=<dir>` to write downloaded inputs, derived panels, and outputs under `<dir>` instead of the repository root, and `SLT=<file>` to point at a local copy of TIC SLT Table 3. `PYTHON`, `RUFF`, and `ROWFLOW` override the executables used by `make`.

Each `make` target chains `rowflow` commands that also run individually. `rowflow --help` lists them, and the [command reference](docs/cli_reference.md) shows the monthly panel steps, the determinant regressions (monthly OLS with lag-3 Newey-West standard errors, set in `config/determinant_specs.yml`), and the commands that build and compare dated vintages of the quarterly rest-of-world Z.1 account.

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

- Results are accounting summaries and conditional associations; they do not estimate causal demand curves or causal effects on domestic liquidity.
- Pre-2023 legacy TIC data (`tressect.txt`) cover long-term Treasury bonds and notes only, while expanded SLT Table 3 from February 2023 onward covers total Treasury securities. The two source periods are labeled separately and are not pooled in determinant regressions.
- TIC and Z.1 differ in frequency, coverage, and revision timing, and neither identifies ultimate beneficial owners beyond reported custodial and counterparty definitions.
- In `build-z1-ledger`, transaction-accounting checks run across the configured Z.1 series, while independent stock checks remain unavailable where dated level, revaluation, or other-volume series are unestablished (for example, gold and Special Drawing Rights holdings).

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
