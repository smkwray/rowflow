# Determinant variable map

This map records the first-pass determinant candidates for the foreign official/private Treasury absorption layer. Status values are descriptive implementation statuses, not claims about identification strength.

The determinant tables are descriptive associations, not causal demand curves. TIC monthly source-defined flows and Z.1 quarterly transactions are separate source concepts. International and regional organizations remain a sidecar category.

## Supply and Issuance

| Candidate | Status | Current column or source | Notes |
|---|---|---|---|
| Net issuance | `available_now` | `marketable_net_issuance_usd_millions` from MSPD Table 1 | Month-to-month change in marketable debt held by public; a stock-change denominator, not gross auction issuance. |
| Gross issuance | `available_now` | `gross_issuance_usd_millions` from `buycurve` accepted amounts | Curated into `rowflow_panel.csv` by `make real-package`; used as an episode denominator and optional standardized regressor. |
| Bill share | `available_now` | `bill_share` | Imported from sibling diagnostics and standardized as `bill_share_z`. |
| Coupon share | `available_from_sibling_but_not_imported` | `buycurve` issuance composition | Defer until a stable public column contract is added. |
| WAM / duration proxy | `available_now` | `wam_years` | Imported from sibling diagnostics and standardized as `wam_or_duration_proxy_z`. |

## Returns

| Candidate | Status | Current column or source | Notes |
|---|---|---|---|
| 2-year Treasury yield | `available_now` | `treasury_2y_yield_pct` from qrawatch FRED `DGS2` | Monthly average sidecar. |
| 10-year Treasury yield | `available_now` | `treasury_10y_yield_pct` from qrawatch FRED `DGS10` | Monthly average sidecar. |
| 30-year Treasury yield | `available_now` | `treasury_30y_yield_pct` from qrawatch FRED `DGS30` | Monthly average sidecar. |
| Term premium | `available_now` | `term_premium_10y_pct` from qrawatch FRED `THREEFYTP10` | Monthly average of the Kim-Wright 10-year term-premium series as carried by qrawatch. |
| Real yield | `needs_public_download` | FRED / Treasury TIPS series | Defer until source and maturity choice are documented. |

## FX and Risk

| Candidate | Status | Current column or source | Notes |
|---|---|---|---|
| Broad dollar | `available_now` | `broad_dollar_index` from FRED `DTWEXBGS` | Monthly average of the nominal broad U.S. dollar index, goods and services. |
| VIX | `available_now` | `vix_index` from qrawatch FRED `VIXCLS` | Monthly average sidecar. |

## Plumbing

| Candidate | Status | Current column or source | Notes |
|---|---|---|---|
| Reserves | `available_now` | `reserves_usd_millions` | Imported from `liqsub`; descriptive diagnostic only. |
| ON RRP | `available_now` | `on_rrp_usd_millions` | Imported from `liqsub`; descriptive diagnostic only. |
| TGA | `available_now` | `tga_usd_millions` | Imported from `liqsub`; descriptive diagnostic only. |
| Fed Treasury holdings | `available_now` | `fed_treasury_holdings_usd_millions` from qrawatch FRED `TREAST` | Month-end-style last observation in month; descriptive stock sidecar only. |
| Marketable debt stock | `available_now` | `marketable_debt_usd_millions` from MSPD Table 1 | Marketable debt held by public stock; used as an episode stock denominator. |
| MMF assets | `available_now` | `mmf_assets_usd_millions` | Imported from `liqsub`; not yet in the first determinant spec block. |

## Reserve Motives

| Candidate | Status | Current column or source | Notes |
|---|---|---|---|
| Global reserves | `defer` | IMF/FRED/public reserve aggregates | Out of first-pass baseline. |
| COFER proxy | `defer` | IMF COFER | Lower frequency and source-boundary work needed before use. |
| IRFCL proxy | `defer` | IMF/FRED reserve series | Defer until a reserve-motive sidecar design exists. |

## Current First-Pass Model Inputs

The current determinant panel uses these available standardized regressors when present:

- `bill_share_z`
- `net_issuance_z`
- `gross_issuance_z`
- `wam_or_duration_proxy_z`
- `treasury_2y_yield_z`
- `treasury_10y_yield_z`
- `treasury_30y_yield_z`
- `term_premium_10y_z`
- `vix_z`
- `reserves_z`
- `on_rrp_z`
- `tga_z`
- `fed_treasury_holdings_z`

The current determinant table writer labels inference as `hac_newey_west_lag_3` under the default monthly spec.
