# rowflow

`rowflow` is a starter package for descriptive rest-of-world Treasury absorption accounting in the Treasury Deposit Channel system. In this project family, **TDC** means the Treasury Deposit Channel as defined upstream by [`smkwray/tdcest`](https://github.com/smkwray/tdcest), the canonical quarterly estimator used as the TDC anchor.

The first package splits foreign Treasury absorption into **foreign official** and **foreign private** components, then joins that split to Treasury maturity composition and domestic liquidity diagnostics. The goal is to clarify *who absorbed Treasury supply*. It is not a causal design for domestic liquidity effects.

## Claim boundary

This repo is designed for public-safe descriptive accounting.

Allowed claims:

- foreign Treasury absorption can be summarized separately for official and private foreign holders;
- TIC and Z.1 give complementary official/private views with different frequency, source definitions, and revisions;
- bill share, weighted-average maturity, TGA, reserves, deposits, MMFs, ON RRP, and TDC anchors are diagnostics for interpretation.

Not allowed without a stronger design:

- causal claims about domestic deposit, reserve, MMF, or yield effects;
- country-level beneficial-owner claims beyond source definitions;
- claims that TIC transactions and Z.1 transactions are interchangeable;
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

These commands are implemented as real CLI entrypoints and can be run against fixture data immediately.

```bash
rowflow validate-config
rowflow validate-sibling-sources --sibling-root ..
rowflow copy-sibling-outputs --sibling-root ..

rowflow build-tic-row-panel \
  --input data/imported/tic/slt_table3.txt \
  --output data/derived/tic_row_monthly.csv

rowflow build-z1-row-panel \
  --input data/imported/z1/z1_row_official_private.csv \
  --output data/derived/z1_row_quarterly.csv

rowflow build-z1-row-panel-from-fred-levels \
  --official-level-json data/imported/fp-tdc/BOGZ1FL263061130Q.observations.json \
  --private-level-json data/imported/fp-tdc/BOGZ1FL263061145Q.observations.json \
  --output data/derived/z1_row_quarterly_real.csv

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
  --figure-dir output/figures

rowflow write-output-manifest --output output/manifests/rowflow_manifest.json
rowflow validate-rowflow-package --strict
```

For a no-external-data smoke build, use the CSV files under `tests/fixtures/` as inputs. The tests show the complete fixture pipeline.

For a local real-data backend build with sibling repositories present, run:

```bash
make real-package
```

The real-data target uses the project external virtual environment by default. It builds the TIC panel from the reused local TIC cache and uses local Z.1/FRED level observations as explicitly labeled level-change context when transaction extracts are not available.

## Source strategy

`rowflow` should reuse sibling outputs before downloading or transforming new data:

- `buycurve`: Treasury issuance composition, bill share, WAM, buyer mix, and TIC bridge context.
- `tdcladder`: maturity/liquidity ladder context.
- `liqsub`: deposits, MMFs, ON RRP, reserves, TGA, and plumbing diagnostics.
- `bankcap`: H.8 bank-group mechanism context.
- `tdcest`: canonical quarterly TDC anchors.
- `tdcpass`: pass-through context.
- `tdcatlas`: episode framing.
- `fp-tdc`: optional local FRED/Z.1 level cache for official/private ROW Treasury level context.

The source contracts in `config/source_contracts.yml` record preferred sibling artifacts and the primary public sources to use only after reusable sibling artifacts are unavailable or insufficient.

## Expected package layout

```text
rowflow/
  config/                 # public metadata, contracts, variable curation, schemas
  docs/                   # public design and source notes
  src/rowflow/            # Python package and CLI implementation
  tests/fixtures/         # tiny fixture inputs; no external data required
  data/                   # ignored local raw/imported/derived data folders
  output/                 # ignored local reports, figures, and manifests
  do/                     # local handoff/todo notes; ignored by .gitignore
```

## First implementation target

The minimum publishable build is a monthly TIC official/private Treasury-flow panel, a quarterly Z.1 official/private comparison panel, a merged diagnostic panel, and one accounting report with a small figure set showing official-led versus private-led foreign absorption episodes.
