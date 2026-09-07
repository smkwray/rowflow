# Quarterly ROW sources and uses

The ledger is descriptive legal-holder accounting. It cannot identify which
dollars financed Treasury purchases or an exclusive foreign deposit offset.
The default sample is 2002Q1–2025Q4. The March 19, 2026 source vintage is frozen;
June 11 is a separate revision comparison. September 11 remains pending until
its final release; preview data cannot overwrite either retained vintage.

`config/row_ledger.yml` defines mutually exclusive asset, liability and equity
leaves separately from totals, subtotals and memo rows. The loader accepts actual
Federal Reserve `FU…Q` unadjusted transactions in USD millions. Native Fed
identifiers are retained exactly; FRED-sidecar receipts retain the actual
`BOGZ1…` identifier and returned vintage label. FA/4 is never substituted for FU.

The [Fed archive](https://www.federalreserve.gov/releases/z1/release-dates.htm)
provides dated CSV bundles and dictionaries. Only selected table members are
retained. Their receipt records the archive URL, release vintage, retrieval
time, archive hash and individual member hashes. Source files are verified
before calculation. Existing source directories are never overwritten.

For acquisition use `rowflow download-z1-archive --vintage YYYY-MM-DD --table
TABLE --output DIRECTORY`, repeating `--table` for each needed table. March
tables: `fu133 l133 fu201 l201 fu202 l202 fu203 l203 fu204 l204`. June tables:
`S2_t_tu S2_s F2_t_tu F2_s F2_1_t_tu F2_1_s F2_2_t_tu F2_2_s F2_3_t_tu
F2_3_s S2_i_q`. Each table includes its matching data dictionary.

Use `rowflow download-z1-sidecars --vintage YYYY-MM-DD --output
DIRECTORY/alfred` for the configured time-deposit issuer and Treasury
revaluation series. The ALFRED response must identify the exact requested
series and vintage in its column heading.

```bash
rowflow build-z1-ledger --input data/raw/z1/2026-03-19 --output output/row_ledger/2026-03-19
rowflow build-z1-ledger --input data/raw/z1/2026-06-11 --output output/row_ledger/2026-06-11
rowflow write-z1-revision-bridge --frozen output/row_ledger/2026-03-19 --revised output/row_ledger/2026-06-11 --output output/row_ledger/revision_bridge.csv
```

The build writes the ledger, crosswalk, deposit bridge, individual numerical
checks, stock-bridge diagnostics and hashed summary. Exit 1 retains diagnostics
and means certification is incomplete or failed. Missing FR/FV is never zero;
an adjustment constructed to force closure is never independent certification.
The rounding envelope is half the sum of absolute coefficients times each
source cell's displayed increment, plus a fixed floating-point allowance. Every
observed gap and bound is printed in the certification CSV.

The [currency bundle](https://www.federalreserve.gov/apps/fof/SeriesAnalyzer.aspx?s=FU263020005&t=&bc=&suf=Q)
splits into currency `263025003` and checkable deposits `263027003`.
The [US-chartered checkable claim](https://www.federalreserve.gov/apps/fof/SeriesAnalyzer.aspx?s=FU763122605&t=&bc=&suf=Q)
equals total ROW checkable deposits less FBO deposits `753122603` and the net
central-bank ROW deposit liability `713122605`. The latter includes foreign
official and international-organization accounts less the IMF reserve position;
it is not a standalone private-bank deposit claim.

The [US-chartered time claim](https://www.federalreserve.gov/apps/fof/SeriesAnalyzer.aspx?s=FU763135265&t=&bc=&suf=Q)
is `763135265 = 263030005 − 753135263`. These issuer splits are tested against
the totals. US-chartered claims are flagged against deposit outcome
`BOGZ1FL764100005Q`; FBO and central-bank claims are excluded. The published
split does not supply a separate affiliated-area ROW deposit amount: none is
invented. Interbank claims remain separate, with US-chartered and FBO issuer
detail and an explicit unresolved claim-class flag.

Deposits are holder-composition measurements, including source allocations;
they do not establish aggregate deposit creation or settlement incidence.
The [series-structure guide](https://www.federalreserve.gov/apps/fof/SeriesStructure.aspx)
separates FU, FR, FV and FL/LM. Quarterly stock changes cannot replace transactions.
