import json
import math
import random
import statistics
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict


@dataclass
class TheoryInputs:
    start_value: float = 75000.0
    power_growth_mean: float = 0.15
    power_growth_std: float = 0.04
    efficiency_improvement_mean: float = 0.07
    efficiency_improvement_std: float = 0.02
    lag_start: float = 0.50
    lag_decay: float = 0.15
    energy_price_mean: float = 0.05
    energy_price_std: float = 0.015
    years: int = 15
    iterations: int = 2000
    random_seed: int = 21


@dataclass
class YearPoint:
    year_index: int
    value: float
    power_growth: float
    efficiency_improvement: float
    energy_price: float
    energy_productivity: float
    miner_margin_proxy: float


@dataclass
class SimulationSummary:
    p10_final_value: float
    p50_final_value: float
    p90_final_value: float
    mean_final_value: float
    min_final_value: float
    max_final_value: float
    mean_final_margin_proxy: float
    mean_final_energy_productivity: float


class PowerEfficiencyMonteCarloSimulator:
    """
    Additive next-step simulation for Power Efficiency Theory.

    This version keeps the core spirit of the prior files:
    - compounding from power growth and efficiency improvement
    - lag/contraction decay

    But it improves the simulation layer by adding:
    - stochastic scenario generation
    - energy-price pressure
    - an energy-productivity metric
    - a miner-margin proxy
    - percentile outputs for more realistic planning
    """

    def __init__(self, inputs: TheoryInputs | None = None) -> None:
        self.inputs = inputs or TheoryInputs()
        random.seed(self.inputs.random_seed)

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def _draw_rate(self, mean: float, std: float, low: float, high: float) -> float:
        return self._clamp(random.gauss(mean, std), low, high)

    def _simulate_single_path(self) -> List[YearPoint]:
        points: List[YearPoint] = []
        current_value = self.inputs.start_value

        for t in range(self.inputs.years + 1):
            if t == 0:
                power_growth = self.inputs.power_growth_mean
                efficiency_improvement = self.inputs.efficiency_improvement_mean
                energy_price = self.inputs.energy_price_mean
            else:
                power_growth = self._draw_rate(
                    self.inputs.power_growth_mean,
                    self.inputs.power_growth_std,
                    -0.20,
                    0.60,
                )
                efficiency_improvement = self._draw_rate(
                    self.inputs.efficiency_improvement_mean,
                    self.inputs.efficiency_improvement_std,
                    0.0,
                    0.40,
                )
                energy_price = self._draw_rate(
                    self.inputs.energy_price_mean,
                    self.inputs.energy_price_std,
                    0.01,
                    0.25,
                )

                growth_factor = (1 + power_growth) / (1 - efficiency_improvement)
                lag_term = 1 - self.inputs.lag_start * ((1 - self.inputs.lag_decay) ** t)
                energy_penalty = 1 / (1 + (energy_price * 4.0))
                current_value = current_value * growth_factor * lag_term * energy_penalty

            energy_productivity = (1 + power_growth) / max(1e-9, (1 - efficiency_improvement) * (1 + energy_price))
            miner_margin_proxy = max(0.0, energy_productivity - 1.0)

            points.append(
                YearPoint(
                    year_index=t,
                    value=current_value,
                    power_growth=power_growth,
                    efficiency_improvement=efficiency_improvement,
                    energy_price=energy_price,
                    energy_productivity=energy_productivity,
                    miner_margin_proxy=miner_margin_proxy,
                )
            )

        return points

    def run(self) -> Dict:
        all_paths = [self._simulate_single_path() for _ in range(self.inputs.iterations)]
        final_values = sorted(path[-1].value for path in all_paths)
        final_margins = [path[-1].miner_margin_proxy for path in all_paths]
        final_productivity = [path[-1].energy_productivity for path in all_paths]

        def percentile(sorted_values: List[float], q: float) -> float:
            if not sorted_values:
                return 0.0
            idx = int((len(sorted_values) - 1) * q)
            return sorted_values[idx]

        summary = SimulationSummary(
            p10_final_value=percentile(final_values, 0.10),
            p50_final_value=percentile(final_values, 0.50),
            p90_final_value=percentile(final_values, 0.90),
            mean_final_value=statistics.fmean(final_values),
            min_final_value=min(final_values),
            max_final_value=max(final_values),
            mean_final_margin_proxy=statistics.fmean(final_margins),
            mean_final_energy_productivity=statistics.fmean(final_productivity),
        )

        representative_paths = {
            "bearish_p10": [asdict(point) for point in min(all_paths, key=lambda p: abs(p[-1].value - summary.p10_final_value))],
            "base_p50": [asdict(point) for point in min(all_paths, key=lambda p: abs(p[-1].value - summary.p50_final_value))],
            "bullish_p90": [asdict(point) for point in min(all_paths, key=lambda p: abs(p[-1].value - summary.p90_final_value))],
        }

        return {
            "inputs": asdict(self.inputs),
            "summary": asdict(summary),
            "representative_paths": representative_paths,
        }


def save_results(results: Dict, output_path: str) -> None:
    Path(output_path).write_text(json.dumps(results, indent=2), encoding="utf-8")


def main() -> None:
    simulator = PowerEfficiencyMonteCarloSimulator()
    results = simulator.run()
    output_path = "power_efficiency_monte_carlo_results.json"
    save_results(results, output_path)

    summary = results["summary"]
    print("Power Efficiency Theory Monte Carlo Simulation")
    print("=" * 48)
    print(f"P10 final value: ${summary['p10_final_value']:,.2f}")
    print(f"P50 final value: ${summary['p50_final_value']:,.2f}")
    print(f"P90 final value: ${summary['p90_final_value']:,.2f}")
    print(f"Mean final value: ${summary['mean_final_value']:,.2f}")
    print(f"Mean final margin proxy: {summary['mean_final_margin_proxy']:.4f}")
    print(f"Mean final energy productivity: {summary['mean_final_energy_productivity']:.4f}")
    print(f"Saved results to: {output_path}")


if __name__ == "__main__":
    main()
