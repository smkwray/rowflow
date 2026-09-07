# Source notes

## TIC official/private Treasury flows

Primary source after sibling reuse: Treasury International Capital Securities (A), with two explicitly labeled regimes.

Expanded source for February 2023 forward: SLT Table 3, `U.S. Treasury Securities Held by Foreign Residents`.

- Landing page: https://home.treasury.gov/data/treasury-international-capital-tic-system
- Securities (A) documentation: https://home.treasury.gov/data/treasury-international-capital-tic-system-home-page/tic-forms-instructions/securities-a-us-transactions-with-foreign-residents-in-long-term-securities
- Table 3 text file: https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/slt_table3.txt
- Legacy sector text file: https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/tressect.txt

Important implementation notes:

- Positive `Net U.S. Sales` denotes an increase in a foreign position.
- Expanded SLT sector rows: `99990` for `Of Which: Foreign Official`, `99991` for `Of Which: Foreign Non-Official`, `79995` for international/regional organizations, and `99996` for `Grand Total`.
- Columns to start with: `for_treas_net` for total Treasury net flow, `for_lt_treas_net` for long-term Treasury net flow, and `for_st_treas_net` for short-term Treasury net flow.
- The legacy `tressect.txt` bridge provides foreign official institutions, other foreigners, and international/regional organizations for net purchases of Treasury bonds and notes. It is long-term-only and must be labeled separately from the expanded total-Treasury SLT concept.
- International/regional organizations are a third sidecar category. They should not be folded into private foreign absorption.
- February 2023 begins the expanded SLT-based table family. Earlier S-form-based files can be stitched only with `tic_source_regime` and `tic_treasury_flow_scope` labels preserved.

## Z.1 ROW official/private comparison

Primary source after sibling reuse: Federal Reserve Z.1, with FRED as a convenient mirror for exact series IDs.

- Z.1 landing page: https://www.federalreserve.gov/releases/z1/
- Official Treasury level: `BOGZ1FL263061130Q`
- Official Treasury transactions: `BOGZ1FU263061130Q`
- Private Treasury level: `BOGZ1FL263061145Q`
- Private Treasury transactions: `BOGZ1FU263061145Q`

The preferred comparison is a Z.1 transaction extract when both official and private transaction series are available. When only local level-series caches are available, `rowflow` computes quarter-over-quarter level changes and labels those columns as level-change context. Level changes should not be described as Z.1 transaction flows.

The real backend build downloads FRED graph CSVs for `BOGZ1FU263061130Q` and `BOGZ1FU263061145Q`, merges them by observation date, and uses those quarterly transaction values directly. It also carries `BOGZ1FL263061130Q` and `BOGZ1FL263061145Q` levels for stock-vs-flow figures. The `FA` series are SAAR flows and should be divided by four if used; the `FU` series are already quarterly transaction amounts.

## Diagnostic sources

Reuse these sibling panels before pulling raw data:

- `buycurve/data/clean/monthly_issuance_maturity_panel.csv` for bill share and WAM.
- `liqsub/data/clean/monthly_liquidity_substitution_panel.csv` for TGA, reserves, deposits, MMFs, and ON RRP.
- `tdcest/data/processed/tdc_estimates.csv` for quarterly TDC anchors.
- `tdcladder`, `bankcap`, `tdcpass`, and `tdcatlas` sidecars when present.
- A local FRED/Z.1 level cache from another project can be used as an optional accelerator for official/private Z.1 level context, but only with level-change labels.

## Determinant layer sources

The determinant layer starts from the built `rowflow_panel.csv`, not from a new raw-data scrape. It preserves `tic_source_regime` and `tic_treasury_flow_scope` so the pre-2023 legacy long-term bridge is not pooled as the same measurement regime as the February 2023-forward expanded SLT total-Treasury data.

The first-pass determinant panel standardizes only variables already present in `rowflow_panel.csv`. Gross issuance is curated from `buycurve` accepted auction amounts and reported in USD millions. Optional qrawatch FRED core data add monthly Treasury yield, Kim-Wright term-premium, VIX, and Fed Treasury holdings sidecars when available. The broad-dollar control uses the public FRED graph CSV for `DTWEXBGS`, the nominal broad U.S. dollar index for goods and services. Missing candidate variables are recorded in `output/tables/determinant_panel_missingness.csv` rather than silently invented.

MSPD Table 1 from FiscalData is reused through `qrawatch` when available. `rowflow` uses the `Total Marketable` row to carry `marketable_debt_usd_millions` as marketable debt held by public and computes `marketable_net_issuance_usd_millions` as the month-to-month change in that stock. This is a redemption-adjusted stock-change denominator, not a gross auction issuance measure.

The FRED sidecars are treated as descriptive market and balance-sheet context. Daily yield, term-premium, VIX, and broad-dollar series are monthly averaged; the Fed Treasury holdings stock uses the last non-missing observation in the month. These controls do not turn the determinant table into a causal demand or liquidity model.

The full determinant table uses OLS coefficients with a local Newey-West/HAC covariance helper and labels inference as `hac_newey_west_lag_3` under the default monthly spec. `monthly_tic_determinants_compact.csv` and `monthly_tic_determinants_compact.md` are derived presentation surfaces: they pivot official and private coefficients side by side, drop intercepts, and rank rows by the stronger absolute t-stat. They should be cited as compact summaries of descriptive associations, not as separate models.

## Dated ROW ledger

See [Quarterly ROW sources and uses](row_ledger.md) for archived FU inputs, issuer mapping, precision bounds, revision comparisons and explicit certification failures. Expanded Treasury totals from February 2023 combine reported SLT notes/bonds transactions with bills estimated from BL2 position changes.
