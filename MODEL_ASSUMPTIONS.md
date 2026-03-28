# Model Assumptions

## Purpose
This document explains the assumptions behind the additive Monte Carlo simulation layer for Power Efficiency Theory.

## Core structure retained from prior files
The new simulation keeps the core logic already visible in the repo:
- value begins from a starting level
- power growth increases productive capacity
- efficiency improvement lowers the energy burden per unit of output
- lag/contraction gradually decays over time

## New assumptions added

### 1. Uncertainty matters
The future is not a single deterministic line.
For that reason, the model draws yearly values from distributions rather than using one fixed annual rate only.

### 2. Energy price pressure matters
The original theory emphasizes computational productivity per unit of energy.
A practical simulation therefore needs an energy-price input, because real miners operate under energy cost pressure.

### 3. Margin should be approximated
The current model introduces a simple `miner_margin_proxy` rather than claiming to calculate true profitability.
This is intentionally conservative. It is a directional indicator, not an accounting statement.

### 4. Percentiles are more useful than one answer
The model reports P10, P50, and P90 outcomes to make the simulation useful for:
- research
- scenario analysis
- decision support
- premium reporting

## Non-claims
This model does **not** yet claim to fully model:
- difficulty adjustments
- Bitcoin issuance schedule effects
- transaction-fee volatility
- hardware capex schedules
- financing costs
- real-world fleet turnover
- exact miner revenue formulas

## Why this still helps
Even without full mining economics, the model is already more commercially useful because it translates Power Efficiency Theory into:
- uncertainty-aware scenario outputs
- operator/investor framing
- exportable research-ready data

## Recommended future upgrades
- add difficulty and reward regime assumptions
- add explicit ASIC generation trajectories
- add energy-cost bands by geography
- add network-level scenario overlays
- add chart-ready percentile band visualization
