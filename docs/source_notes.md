# Source notes

## TIC official/private Treasury flows

Primary source after sibling reuse: Treasury International Capital Securities (A), SLT Table 3, `U.S. Treasury Securities Held by Foreign Residents`.

- Landing page: https://home.treasury.gov/data/treasury-international-capital-tic-system
- Securities (A) documentation: https://home.treasury.gov/data/treasury-international-capital-tic-system-home-page/tic-forms-instructions/securities-a-us-transactions-with-foreign-residents-in-long-term-securities
- Table 3 text file: https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/slt_table3.txt

Important implementation notes:

- Positive `Net U.S. Sales` denotes an increase in a foreign position.
- Sector rows to start with: `99990` for `Of Which: Foreign Official`, `99991` for `Of Which: Foreign Non-Official`, and `99996` for `Grand Total`.
- Columns to start with: `for_treas_net` for total Treasury net flow, `for_lt_treas_net` for long-term Treasury net flow, and `for_st_treas_net` for short-term Treasury net flow.
- February 2023 begins the expanded SLT-based table family. Earlier S-form-based files need separate handling and should not be silently stitched without a documented bridge.

## Z.1 ROW official/private comparison

Primary source after sibling reuse: Federal Reserve Z.1, with FRED as a convenient mirror for exact series IDs.

- Z.1 landing page: https://www.federalreserve.gov/releases/z1/
- Official Treasury level: `BOGZ1FL263061130Q`
- Official Treasury transactions: `BOGZ1FU263061130Q`
- Private Treasury level: `BOGZ1FL263061145Q`
- Private Treasury transactions: `BOGZ1FU263061145Q`

The preferred comparison is a Z.1 transaction extract when both official and private transaction series are available. When only local level-series caches are available, `rowflow` computes quarter-over-quarter level changes and labels those columns as level-change context. Level changes should not be described as Z.1 transaction flows.

## Diagnostic sources

Reuse these sibling panels before pulling raw data:

- `buycurve/data/clean/monthly_issuance_maturity_panel.csv` for bill share and WAM.
- `liqsub/data/clean/monthly_liquidity_substitution_panel.csv` for TGA, reserves, deposits, MMFs, and ON RRP.
- `tdcest/data/processed/tdc_estimates.csv` for quarterly TDC anchors.
- `tdcladder`, `bankcap`, `tdcpass`, and `tdcatlas` sidecars when present.
- A local FRED/Z.1 level cache from another project can be used as an optional accelerator for official/private Z.1 level context, but only with level-change labels.
