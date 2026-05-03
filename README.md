# rowflow

`rowflow` is a planned accounting-refinement project for the Treasury Deposit
Channel system. It will split rest-of-world Treasury absorption into foreign
official and foreign private components, then compare those flows with Treasury
maturity composition and domestic liquidity diagnostics.

The project should stay descriptive unless a stronger identification design is
explicitly built. Its first role is to clarify who absorbed Treasury supply, not
to claim causal domestic liquidity effects.

## Initial Scope

- Build a monthly TIC official/private Treasury-flow panel.
- Build a quarterly Z.1 rest-of-world official/private comparison panel.
- Reuse sibling outputs from `buycurve`, `tdcladder`, `liqsub`, `bankcap`,
  `tdcest`, and `tdcatlas` before downloading new data.
- Produce a compact accounting report and figures showing official-led versus
  private-led foreign absorption episodes.

## Install

Create a virtual environment outside the repository:

```bash
python -m venv ~/venvs/rowflow
source ~/venvs/rowflow/bin/activate
python -m pip install -e '.[dev]'
```

