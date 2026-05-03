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

The real backend build downloads FRED graph CSVs for `BOGZ1FU263061130Q` and `BOGZ1FU263061145Q`, merges them by observation date, and uses those quarterly transaction values directly. The `FA` series are SAAR flows and should be divided by four if used; the `FU` series are already quarterly transaction amounts.

## Diagnostic sources

Reuse these sibling panels before pulling raw data:

- `buycurve/data/clean/monthly_issuance_maturity_panel.csv` for bill share and WAM.
- `liqsub/data/clean/monthly_liquidity_substitution_panel.csv` for TGA, reserves, deposits, MMFs, and ON RRP.
- `tdcest/data/processed/tdc_estimates.csv` for quarterly TDC anchors.
- `tdcladder`, `bankcap`, `tdcpass`, and `tdcatlas` sidecars when present.
- A local FRED/Z.1 level cache from another project can be used as an optional accelerator for official/private Z.1 level context, but only with level-change labels.
