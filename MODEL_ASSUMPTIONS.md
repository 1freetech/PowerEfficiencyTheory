# Model Assumptions

## Purpose
Power Efficiency Theory (PEI) is a research/scenario framework for studying how growth in productive computational power and improvements in energy efficiency can compound over time. It is not a Bitcoin price forecast, miner profit-and-loss model, or investment recommendation.

## Core deterministic model
For year index `x`:

- power multiplier: `(1 + p)^x`
- efficiency multiplier: `(1 / (1 - e))^x`
- combined PEI multiplier: `((1 + p) / (1 - e))^x`
- lag factor: `1 - L * (1 - d)^x`
- unlagged PEI value: `V0 * PEI multiplier`
- lag-adjusted PEI value: `unlagged PEI value * lag factor`

`V0` is the reference value before the convergence/lag adjustment. Because the lag factor is applied at `x = 0`, the first lag-adjusted plotted value can be below `V0` when `L > 0`. The chart now shows both the unlagged and lag-adjusted paths so that assumption is visible rather than hidden.

## Power and efficiency
`p` is the assumed annual growth rate in productive computational power. `e` is the assumed annual improvement in energy required per unit of output, represented as an efficiency multiplier of `1 / (1 - e)`. These are model inputs, not guaranteed future rates.

## Lag / convergence
`L` represents the initial gap between the theoretical PEI path and the lag-adjusted path. `d` controls how quickly that gap decays. Inputs are constrained to economically interpretable ranges so the lag factor cannot create a negative modeled value.

## Pathwise Monte Carlo uncertainty
The PEI uncertainty band now simulates compounded paths rather than adding independent noise to each chart point. Each path draws annual power-growth and efficiency-improvement rates around the user inputs and draws a path-level lag-decay rate. P10, P50, and P90 therefore reflect uncertainty that accumulates through time.

The Monte Carlo layer is still an assumption-driven sensitivity model. Its distributions are not calibrated to a claim of historical return probabilities unless separate empirical calibration is supplied.

## Network-regime overlay
The network-regime layer is a directional proxy that adds uncertain:
- network difficulty growth
- transaction-fee pressure
- energy-price pressure
- PEI power growth
- PEI efficiency improvement

These variables compound through time. The lag factor is applied once to each modeled year rather than repeatedly multiplying the prior year's lagged value.

The network-regime output is **not** a full Bitcoin mining economics model. Difficulty, fees, and energy prices are simplified proxies rather than exact protocol, fleet, accounting, or market models.

## Not yet modeled explicitly
The repository does not yet claim to fully model:
- Bitcoin subsidy halvings and issuance schedule
- transaction-fee distributions by block or cycle
- ASIC purchase price, depreciation, financing, and replacement schedules
- fleet-level uptime, curtailment, pool fees, repairs, and hosting contracts
- geographic power-market structure and demand-response revenue
- taxes, capital structure, or corporate overhead
- empirically calibrated covariance among PEI, difficulty, fees, energy, and market price

## Chart interpretation
The primary chart distinguishes:
- unlagged theoretical PEI value
- lag-adjusted PEI value
- pathwise Monte Carlo P10–P90 band
- Monte Carlo P50
- optional observed-market benchmark supplied by the user

The driver panel separately shows power, efficiency, and combined PEI multipliers plus the lag factor. This decomposition is intended to make the assumptions auditable instead of hiding them inside one projected line.

## Recommended future upgrades
- empirical calibration against historical hashrate and ASIC efficiency series
- explicit Bitcoin subsidy/fee revenue model
- fleet-turnover and ASIC-generation trajectories
- geographic energy-cost and curtailment scenarios
- covariance/correlation assumptions for stochastic drivers
- backtesting and out-of-sample error reporting
