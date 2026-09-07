# Public claim boundaries

`rowflow` should be framed as descriptive accounting infrastructure.

Use language like:

> This report splits foreign Treasury absorption into official and private components and compares those components with maturity and liquidity diagnostics.

Avoid language like:

> Foreign official purchases caused deposits to rise.

The first version can say when foreign absorption was official-led or private-led under the source sign convention. It cannot identify causal domestic liquidity effects, estimate structural incidence, or infer beneficial ownership behind custodial/financial-center reporting without additional evidence.

For the determinant layer, use language like:

> The determinant tables are descriptive associations, not causal demand curves.

Avoid language like:

> Reserve changes caused foreign official Treasury purchases.

Additional boundaries:

- TIC monthly source-defined flows and Z.1 quarterly transactions are separate source concepts.
- Auction allotments, if later used, are primary-market allocation signals rather than final-holder measures.
- Country-level TIC data, if later added, should be interpreted as source-location data rather than beneficial-owner evidence.
- Ordinary OLS standard errors must not be labeled as HAC/Newey-West; determinant tables may use the `hac_newey_west_lag_*` label only when the HAC covariance helper is actually used.
- Compact determinant presentation tables and Markdown companions are derived summaries of the full descriptive determinant table; they should not be described as separate evidence, causal rankings, or model-selection proof.
