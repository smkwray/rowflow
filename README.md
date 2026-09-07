# rowflow

`rowflow` is a descriptive rest-of-world Treasury absorption accounting package for the Treasury Deposit Channel system. In this project family, **TDC** means the Treasury Deposit Channel as defined upstream by [`smkwray/tdcest`](https://github.com/smkwray/tdcest), the canonical quarterly estimator used as the TDC anchor.

The package splits foreign Treasury absorption into **foreign official**, **foreign private**, and separately tracked international/regional organization components, then joins that split to Treasury maturity composition and domestic liquidity diagnostics. The goal is to clarify *who absorbed Treasury supply*. It is not a causal design for domestic liquidity effects.

The Phase 2 determinant layer adds source-regime ledgers, episode absorption accounting, a monthly determinant panel, and first-pass official/private determinant tables. These outputs are exploratory descriptive associations, not causal demand curves.

## Current result

The current real backend build supports one main interpretation: foreign official institutions remain a large Treasury stock holder base, but recent marginal rest-of-world Treasury absorption is mostly private-led.

Current local real-package outputs:

- `data/derived/tic_row_monthly_real.csv`: 578 monthly rows, `1978-01..2026-02`.
- `data/derived/z1_row_quarterly_real.csv`: 302 transaction-supported quarters, `1946Q4..2025Q4`, with matched Z.1 level columns for stock-vs-flow figures.
- `data/derived/rowflow_panel.csv`: 578 monthly rows joining TIC flows, source-regime labels, IRO sidecars, Z.1 transaction context, liquidity diagnostics, Treasury supply/debt denominators, FRED market sidecars, and TDC anchors.
- `output/tables/rowflow_results_summary.csv`: compact results table for paper/deck use.
- `output/figures/stock_vs_flow.svg`: figure showing official/private Z.1 stock context against recent TIC transaction flows.

Current local determinant outputs from `make real-determinants`:

- `output/tables/source_regime_ledger.csv`: TIC legacy, TIC expanded SLT, and Z.1 source-concept ledger.
- `output/tables/episode_absorption.csv`: official/private/IRO episode accounting with net-issuance, gross-issuance, and marketable-debt denominator shares where source coverage is available.
- `data/derived/foreign_absorption_determinants_monthly.csv`: monthly determinant panel with TIC source-regime labels preserved.
- `output/tables/monthly_tic_determinants.csv`: first-pass ordinary OLS descriptive determinant table.
- `output/tables/monthly_tic_determinants_compact.csv`: presentation-oriented official/private coefficient summary derived from the full determinant table.
- `output/reports/monthly_tic_determinants_compact.md`: human-readable companion for the compact determinant table.
- `output/reports/foreign_absorption_determinants.md`: compact determinant-layer report and claim-boundary summary.

Headline recent-window result:

- TIC expanded-SLT window `2023-02..2026-02`: foreign private net Treasury flow is `1,797,270` USD millions, foreign official flow is `289,013` USD millions, and international/regional organizations add a separate `77,485` USD millions sidecar.
- Z.1 recent transaction window `2023Q1..2025Q4`: foreign private transaction flow is `1,698,504` USD millions and foreign official transaction flow is `147,442` USD millions.

## Claim boundary

This repo is designed for public-safe descriptive accounting.

Allowed claims:

- foreign Treasury absorption can be summarized separately for official and private foreign holders;
- international/regional organizations can be carried as a separate sidecar category;
- TIC and Z.1 give complementary official/private views with different frequency, source definitions, and revisions;
- bill share, weighted-average maturity, TGA, reserves, deposits, MMFs, ON RRP, and TDC anchors are diagnostics for interpretation.

Not allowed without a stronger design:

- causal claims about domestic deposit, reserve, MMF, or yield effects;
- country-level beneficial-owner claims beyond source definitions;
- claims that TIC transactions and Z.1 transactions are interchangeable;
- claims that the pre-2023 TIC long-term bonds-and-notes bridge is identical to the February 2023-forward expanded SLT total-Treasury concept;
- claims that reused sibling diagnostics are structural parameters.

## Install

Create a virtual environment outside the repo, then install the package in editable mode.

```bash
python -m venv ~/venvs/rowflow
source ~/venvs/rowflow/bin/activate
python -m pip install -e '.[dev]'
```

Run the fixture-backed tests:

```bash
python -m pytest
```

## Command map

These commands are implemented as CLI entrypoints and can be run against fixture data immediately.

```bash
rowflow validate-config
rowflow validate-sibling-sources --sibling-root ..
rowflow copy-sibling-outputs --sibling-root ..

rowflow build-tic-row-panel \
  --input data/imported/tic/slt_table3.txt \
  --output data/derived/tic_row_monthly.csv

rowflow combine-tic-row-panels \
  --input data/derived/tic_row_monthly_legacy_tressect.csv \
  --input data/derived/tic_row_monthly_slt.csv \
  --output data/derived/tic_row_monthly_real.csv

rowflow download-z1-fred-transactions \
  --output data/raw/z1/z1_row_official_private_transactions.csv

rowflow build-z1-row-panel \
  --input data/imported/z1/z1_row_official_private.csv \
  --output data/derived/z1_row_quarterly.csv

rowflow build-rowflow-panel \
  --tic-panel data/derived/tic_row_monthly.csv \
  --z1-panel data/derived/z1_row_quarterly.csv \
  --diagnostics data/imported/diagnostics/monthly_diagnostics.csv \
  --tdc-context data/imported/tdcest/tdc_estimates.csv \
  --output data/derived/rowflow_panel.csv

rowflow write-rowflow-report \
  --panel data/derived/rowflow_panel.csv \
  --z1-panel data/derived/z1_row_quarterly.csv \
  --output-md output/reports/rowflow_accounting_report.md \
  --figure-dir output/figures \
  --table-dir output/tables

rowflow write-output-manifest --output output/manifests/rowflow_manifest.json
rowflow validate-rowflow-package --strict
```

Determinant-layer commands:

```bash
rowflow write-source-regime-ledger \
  --tic-panel data/derived/tic_row_monthly_real.csv \
  --z1-panel data/derived/z1_row_quarterly_real.csv \
  --output-csv output/tables/source_regime_ledger.csv \
  --output-md output/reports/source_regime_ledger.md

rowflow write-episode-absorption \
  --panel data/derived/rowflow_panel.csv \
  --z1-panel data/derived/z1_row_quarterly_real.csv \
  --episodes config/episodes.yml \
  --output output/tables/episode_absorption.csv

rowflow build-determinant-panel \
  --panel data/derived/rowflow_panel.csv \
  --spec config/determinant_specs.yml \
  --output data/derived/foreign_absorption_determinants_monthly.csv

rowflow write-determinant-tables \
  --panel data/derived/foreign_absorption_determinants_monthly.csv \
  --spec config/determinant_specs.yml \
  --output output/tables/monthly_tic_determinants.csv

rowflow write-compact-determinant-table \
  --determinants output/tables/monthly_tic_determinants.csv \
  --output output/tables/monthly_tic_determinants_compact.csv

rowflow write-compact-determinant-markdown \
  --compact output/tables/monthly_tic_determinants_compact.csv \
  --output-md output/reports/monthly_tic_determinants_compact.md

rowflow write-determinant-report \
  --panel data/derived/foreign_absorption_determinants_monthly.csv \
  --ledger output/tables/source_regime_ledger.csv \
  --episodes output/tables/episode_absorption.csv \
  --determinants output/tables/monthly_tic_determinants.csv \
  --output-md output/reports/foreign_absorption_determinants.md
```

For a no-external-data smoke build, use the CSV files under `tests/fixtures/` as inputs. The tests show the complete fixture pipeline.

For a local real-data backend build with sibling repositories present, run:

```bash
make real-package
```

The real-data target uses the project external virtual environment by default. It builds the TIC panel from the reused local SLT cache, downloads the public legacy TIC `tressect.txt` bridge for pre-2023 long-term Treasury bonds and notes, downloads public FRED Z.1 `FU` transaction CSVs plus companion `FL` level series, and preserves source-regime labels before writing the real package outputs. The report step writes a compact results table and a stock-vs-flow figure for paper/deck use.

For the real determinant package, run:

```bash
make real-determinants
```

This target runs `make real-package`, writes the determinant ledger, episode table, determinant panel, first-pass determinant table, compact presentation CSV/Markdown, determinant report, manifest, and package validation. The determinant tables use OLS coefficients with a local Newey-West/HAC covariance helper and label inference as `hac_newey_west_lag_3` under the default monthly spec. FRED sidecars add Treasury yield, term-premium, broad-dollar, VIX, and Fed Treasury holdings controls.

## Source strategy

`rowflow` should reuse sibling outputs before downloading or transforming new data:

- [`buycurve`](https://github.com/smkwray/buycurve): Treasury issuance composition, bill share, WAM, buyer mix, and TIC bridge context.
- [`tdcladder`](https://github.com/smkwray/tdcladder): maturity/liquidity ladder context.
- [`liqsub`](https://github.com/smkwray/liqsub): deposits, MMFs, ON RRP, reserves, TGA, and plumbing diagnostics.
- [`bankcap`](https://github.com/smkwray/bankcap): H.8 bank-group mechanism context.
- [`tdcest`](https://github.com/smkwray/tdcest): canonical quarterly TDC anchors.
- [`tdcpass`](https://github.com/smkwray/tdcpass): pass-through context.
- [`tdcatlas`](https://github.com/smkwray/tdcatlas): episode framing.
- [`qrawatch`](https://github.com/smkwray/qrawatch): QRA, Treasury debt-stock, and optional FRED market sidecars.
- [`fp-tdc`](https://github.com/smkwray/fp-tdc): optional local FRED/Z.1 level cache for official/private ROW Treasury level context.

The source contracts in `config/source_contracts.yml` record preferred sibling artifacts and the primary public sources to use only after reusable sibling artifacts are unavailable or insufficient.

## Expected package layout

```text
rowflow/
  config/                 # public metadata, contracts, variable curation, schemas
  docs/                   # public design and source notes
  src/rowflow/            # Python package and CLI implementation
  tests/fixtures/         # tiny fixture inputs; no external data required
  data/                   # ignored local raw/imported/derived data folders
  output/                 # ignored local reports, figures, tables, manifests, and demos
```

## Backend state

The backend and first-pass determinant layer are complete enough for paper/deck support. Remaining work is downstream presentation, paper integration, richer source-side extensions, optional episode overlays from sibling projects, and any stronger identification design. The public package should continue to avoid individual-holder identification and causal domestic-liquidity claims unless a separate identification design is added.
