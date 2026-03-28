import json
import random
import statistics
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List


@dataclass
class NetworkInputs:
    start_value: float = 75000.0
    power_growth_mean: float = 0.15
    power_growth_std: float = 0.04
    efficiency_improvement_mean: float = 0.07
    efficiency_improvement_std: float = 0.02
    difficulty_growth_mean: float = 0.11
    difficulty_growth_std: float = 0.03
    fee_pressure_mean: float = 0.03
    fee_pressure_std: float = 0.02
    energy_price_mean: float = 0.05
    energy_price_std: float = 0.015
    lag_start: float = 0.50
    lag_decay: float = 0.15
    years: int = 15
    iterations: int = 1500
    random_seed: int = 34


class NetworkRegimeSimulator:
    def __init__(self, inputs: NetworkInputs | None = None) -> None:
        self.inputs = inputs or NetworkInputs()
        random.seed(self.inputs.random_seed)

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def _draw(self, mean: float, std: float, low: float, high: float) -> float:
        return self._clamp(random.gauss(mean, std), low, high)

    def _run_path(self) -> List[dict]:
        current_value = self.inputs.start_value
        points: List[dict] = []

        for year in range(self.inputs.years + 1):
            if year == 0:
                power_growth = self.inputs.power_growth_mean
                efficiency_improvement = self.inputs.efficiency_improvement_mean
                difficulty_growth = self.inputs.difficulty_growth_mean
                fee_pressure = self.inputs.fee_pressure_mean
                energy_price = self.inputs.energy_price_mean
            else:
                power_growth = self._draw(self.inputs.power_growth_mean, self.inputs.power_growth_std, -0.2, 0.6)
                efficiency_improvement = self._draw(self.inputs.efficiency_improvement_mean, self.inputs.efficiency_improvement_std, 0.0, 0.4)
                difficulty_growth = self._draw(self.inputs.difficulty_growth_mean, self.inputs.difficulty_growth_std, -0.05, 0.4)
                fee_pressure = self._draw(self.inputs.fee_pressure_mean, self.inputs.fee_pressure_std, -0.05, 0.2)
                energy_price = self._draw(self.inputs.energy_price_mean, self.inputs.energy_price_std, 0.01, 0.25)

                growth_factor = (1 + power_growth) / (1 - efficiency_improvement)
                difficulty_penalty = 1 / (1 + difficulty_growth)
                fee_boost = 1 + fee_pressure
                lag_term = 1 - self.inputs.lag_start * ((1 - self.inputs.lag_decay) ** year)
                energy_penalty = 1 / (1 + energy_price * 4.0)

                current_value = current_value * growth_factor * difficulty_penalty * fee_boost * lag_term * energy_penalty

            resilience_score = ((1 + power_growth) * (1 + fee_pressure)) / max(1e-9, (1 + difficulty_growth) * (1 + energy_price))

            points.append(
                {
                    "year_index": year,
                    "value": current_value,
                    "power_growth": power_growth,
                    "efficiency_improvement": efficiency_improvement,
                    "difficulty_growth": difficulty_growth,
                    "fee_pressure": fee_pressure,
                    "energy_price": energy_price,
                    "resilience_score": resilience_score,
                }
            )

        return points

    def run(self) -> Dict:
        paths = [self._run_path() for _ in range(self.inputs.iterations)]
        finals = sorted(path[-1]["value"] for path in paths)
        resilience = [path[-1]["resilience_score"] for path in paths]

        def percentile(values: List[float], q: float) -> float:
            idx = int((len(values) - 1) * q)
            return values[idx]

        result = {
            "inputs": asdict(self.inputs),
            "summary": {
                "p10_final_value": percentile(finals, 0.10),
                "p50_final_value": percentile(finals, 0.50),
                "p90_final_value": percentile(finals, 0.90),
                "mean_final_value": statistics.fmean(finals),
                "mean_resilience_score": statistics.fmean(resilience),
            },
        }
        return result


def main() -> None:
    simulator = NetworkRegimeSimulator()
    results = simulator.run()
    output = Path("power_efficiency_network_regime_results.json")
    output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Saved results to: {output}")
    print(json.dumps(results["summary"], indent=2))


if __name__ == "__main__":
    main()
