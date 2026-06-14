"""Power Efficiency Theory Simulator 17.0

## What changed in 17.0 and why
- fixes stale validation metadata so the generated artifact reports the correct simulator version instead of an old 8.0 label
- integrates the existing scenario matrix with an explicit network-regime Monte Carlo layer so scheduled upgrades add genuinely new analytical output rather than superficial version churn
- emits new additive 17.0 validation and summary artifacts only, preserving prior user-created files untouched
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from dataclasses import dataclass, asdict
from pathlib import Path


NUMPY_AVAILABLE = True
NUMPY_IMPORT_ERROR: str | None = None
try:
    import numpy as np  # noqa: F401
except Exception as exc:  # pragma: no cover - environment dependent
    NUMPY_AVAILABLE = False
    NUMPY_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
    np = None

GUI_IMPORT_ERROR: str | None = None
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox  # noqa: F401
    from PIL import Image, ImageTk  # noqa: F401
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    GUI_AVAILABLE = True
except Exception as exc:  # pragma: no cover - environment dependent
    GUI_AVAILABLE = False
    GUI_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
    tk = None
    filedialog = None
    messagebox = None
    FigureCanvasTkAgg = None
    Figure = None


@dataclass
class SimulationInputs:
    start_value: float = 75000.0
    power_growth: float = 0.15
    efficiency_improvement: float = 0.07
    lag_start: float = 0.50
    lag_decay: float = 0.15
    start_year: int = 2025
    end_year: int = 2040


@dataclass
class ScenarioDefinition:
    name: str
    power_growth: float
    efficiency_improvement: float
    lag_start: float
    lag_decay: float


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


def _percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        raise ValueError("No values available for percentile calculation.")
    idx = int((len(sorted_values) - 1) * q)
    return sorted_values[idx]


def build_price_series(inputs: SimulationInputs) -> dict:
    if inputs.end_year <= inputs.start_year:
        raise ValueError("End year must be greater than start year.")
    if inputs.efficiency_improvement >= 1:
        raise ValueError("Efficiency improvement must be less than 1.")
    if 1 + inputs.power_growth <= 0:
        raise ValueError("Power growth must keep (1 + p) above 0.")
    if inputs.lag_start >= 1.5:
        raise ValueError("Initial lag is too large for this chart.")

    years = list(range(inputs.start_year, inputs.end_year + 1))
    growth = (1 + inputs.power_growth) / (1 - inputs.efficiency_improvement)
    values = []
    values_m = []
    for year in years:
        x = year - inputs.start_year
        base_value = inputs.start_value * (growth ** x)
        lag_term = 1 - inputs.lag_start * ((1 - inputs.lag_decay) ** x)
        value = base_value * lag_term
        values.append(value)
        values_m.append(value / 1e6)

    return {
        "years": years,
        "raw_values": values,
        "values_m": values_m,
        "growth_ratio": growth,
    }


def build_monte_carlo_overlay(series: dict, iterations: int = 250, seed: int = 42) -> dict:
    if iterations < 10:
        raise ValueError("Monte Carlo iterations must be at least 10.")

    rng = random.Random(seed)
    base_values = series["raw_values"]
    samples: list[list[float]] = []
    for _ in range(iterations):
        curve = []
        for value in base_values:
            noise = max(0.55, min(1.45, rng.gauss(1.0, 0.08)))
            curve.append(value * noise)
        samples.append(curve)

    p10, p50, p90 = [], [], []
    for col in range(len(base_values)):
        column = sorted(sample[col] for sample in samples)
        p10.append(_percentile(column, 0.10))
        p50.append(_percentile(column, 0.50))
        p90.append(_percentile(column, 0.90))

    return {
        "years": series["years"],
        "p10": p10,
        "p50": p50,
        "p90": p90,
    }


def build_default_scenarios(inputs: SimulationInputs) -> list[ScenarioDefinition]:
    return [
        ScenarioDefinition(
            name="base_case",
            power_growth=inputs.power_growth,
            efficiency_improvement=inputs.efficiency_improvement,
            lag_start=inputs.lag_start,
            lag_decay=inputs.lag_decay,
        ),
        ScenarioDefinition(
            name="conservative",
            power_growth=max(inputs.power_growth - 0.04, -0.95),
            efficiency_improvement=max(inputs.efficiency_improvement - 0.02, 0.0),
            lag_start=min(inputs.lag_start + 0.08, 1.49),
            lag_decay=max(inputs.lag_decay - 0.03, 0.01),
        ),
        ScenarioDefinition(
            name="accelerated",
            power_growth=inputs.power_growth + 0.05,
            efficiency_improvement=min(inputs.efficiency_improvement + 0.02, 0.95),
            lag_start=max(inputs.lag_start - 0.08, 0.0),
            lag_decay=min(inputs.lag_decay + 0.03, 0.95),
        ),
    ]


class NetworkRegimeSimulator:
    def __init__(self, inputs: NetworkInputs | None = None) -> None:
        self.inputs = inputs or NetworkInputs()
        random.seed(self.inputs.random_seed)

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def _draw(self, mean: float, std: float, low: float, high: float) -> float:
        return self._clamp(random.gauss(mean, std), low, high)

    def _run_path(self) -> list[dict]:
        current_value = self.inputs.start_value
        points: list[dict] = []

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

    def run(self) -> dict:
        paths = [self._run_path() for _ in range(self.inputs.iterations)]
        finals = sorted(path[-1]["value"] for path in paths)
        resilience = [path[-1]["resilience_score"] for path in paths]

        return {
            "inputs": asdict(self.inputs),
            "summary": {
                "p10_final_value": _percentile(finals, 0.10),
                "p50_final_value": _percentile(finals, 0.50),
                "p90_final_value": _percentile(finals, 0.90),
                "mean_final_value": statistics.fmean(finals),
                "mean_resilience_score": statistics.fmean(resilience),
            },
        }


def build_network_inputs_for_scenario(scenario_inputs: SimulationInputs, iterations: int, seed: int) -> NetworkInputs:
    return NetworkInputs(
        start_value=scenario_inputs.start_value,
        power_growth_mean=scenario_inputs.power_growth,
        power_growth_std=max(0.015, abs(scenario_inputs.power_growth) * 0.25),
        efficiency_improvement_mean=scenario_inputs.efficiency_improvement,
        efficiency_improvement_std=max(0.01, abs(scenario_inputs.efficiency_improvement) * 0.25),
        difficulty_growth_mean=max(0.02, scenario_inputs.power_growth * 0.73),
        difficulty_growth_std=0.03,
        fee_pressure_mean=0.03,
        fee_pressure_std=0.02,
        energy_price_mean=0.05,
        energy_price_std=0.015,
        lag_start=scenario_inputs.lag_start,
        lag_decay=scenario_inputs.lag_decay,
        years=scenario_inputs.end_year - scenario_inputs.start_year,
        iterations=iterations,
        random_seed=seed,
    )


def run_scenario_matrix(inputs: SimulationInputs, iterations: int) -> dict:
    scenarios = build_default_scenarios(inputs)
    matrix: list[dict] = []
    for idx, scenario in enumerate(scenarios):
        scenario_inputs = SimulationInputs(
            start_value=inputs.start_value,
            power_growth=scenario.power_growth,
            efficiency_improvement=scenario.efficiency_improvement,
            lag_start=scenario.lag_start,
            lag_decay=scenario.lag_decay,
            start_year=inputs.start_year,
            end_year=inputs.end_year,
        )
        series = build_price_series(scenario_inputs)
        overlay = build_monte_carlo_overlay(
            series,
            iterations=iterations,
            seed=42 + idx,
        )
        network = NetworkRegimeSimulator(
            build_network_inputs_for_scenario(scenario_inputs, iterations=max(250, iterations * 3), seed=84 + idx)
        ).run()
        matrix.append(
            {
                "name": scenario.name,
                "inputs": asdict(scenario_inputs),
                "growth_ratio": float(series["growth_ratio"]),
                "final_value": float(series["raw_values"][-1]),
                "p10_final": float(overlay["p10"][-1]),
                "p50_final": float(overlay["p50"][-1]),
                "p90_final": float(overlay["p90"][-1]),
                "network_regime": network,
            }
        )
    return {"scenarios": matrix}


def build_summary_text(matrix: dict) -> str:
    scenarios = matrix["scenarios"]
    ranked = sorted(scenarios, key=lambda item: item["final_value"], reverse=True)
    leader = ranked[0]
    trailer = ranked[-1]
    lines = [
        "Power Efficiency Theory 17.0 scenario + network regime summary",
        f"Top deterministic case: {leader['name']} -> final ${leader['final_value']:,.0f} | P50 ${leader['p50_final']:,.0f} | network P50 ${leader['network_regime']['summary']['p50_final_value']:,.0f}",
        f"Lowest deterministic case: {trailer['name']} -> final ${trailer['final_value']:,.0f} | P50 ${trailer['p50_final']:,.0f} | network P50 ${trailer['network_regime']['summary']['p50_final_value']:,.0f}",
        "Scenario table:",
    ]
    for item in ranked:
        net = item["network_regime"]["summary"]
        lines.append(
            "- {name}: growth_ratio={growth_ratio:.4f}, deterministic_final=${final_value:,.0f}, monte_p50=${p50_final:,.0f}, network_p10=${np10:,.0f}, network_p50=${np50:,.0f}, network_p90=${np90:,.0f}, resilience={resilience:.4f}".format(
                name=item["name"],
                growth_ratio=item["growth_ratio"],
                final_value=item["final_value"],
                p50_final=item["p50_final"],
                np10=net["p10_final_value"],
                np50=net["p50_final_value"],
                np90=net["p90_final_value"],
                resilience=net["mean_resilience_score"],
            )
        )
    return "\n".join(lines)


def run_headless_validation(iterations: int = 250) -> dict:
    inputs = SimulationInputs()
    series = build_price_series(inputs)
    overlay = build_monte_carlo_overlay(series, iterations=iterations)
    matrix = run_scenario_matrix(inputs, iterations=iterations)
    summary_text = build_summary_text(matrix)

    final_value = float(series["raw_values"][-1])
    monte_p50 = float(overlay["p50"][-1])
    monte_p10 = float(overlay["p10"][-1])
    monte_p90 = float(overlay["p90"][-1])

    result = {
        "version": "17.0",
        "inputs": asdict(inputs),
        "final_value": final_value,
        "growth_ratio": float(series["growth_ratio"]),
        "monte_carlo": {
            "iterations": iterations,
            "p10_final": monte_p10,
            "p50_final": monte_p50,
            "p90_final": monte_p90,
        },
        "scenario_matrix": matrix,
        "summary_text": summary_text,
        "gui_available": GUI_AVAILABLE,
        "gui_import_error": GUI_IMPORT_ERROR,
        "numpy_available": NUMPY_AVAILABLE,
        "numpy_import_error": NUMPY_IMPORT_ERROR,
    }

    Path("power_efficiency_17_0_validation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    Path("power_efficiency_17_0_summary.txt").write_text(summary_text + "\n", encoding="utf-8")
    return result


if GUI_AVAILABLE and NUMPY_AVAILABLE:
    class ScrollableSidebar(tk.Frame):
        def __init__(self, parent: tk.Widget, bg: str, width: int = 430) -> None:
            super().__init__(parent, bg=bg, width=width)
            self.pack_propagate(False)
            self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0, width=width)
            self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
            self.inner = tk.Frame(self.canvas, bg=bg)
            self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
            self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
            self.canvas.configure(yscrollcommand=self.scrollbar.set)
            self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.window_id, width=e.width))
            self.canvas.pack(side="left", fill="both", expand=True)
            self.scrollbar.pack(side="right", fill="y")

    class PowerEfficiencySimulator:
        def __init__(self, root: tk.Tk) -> None:
            self.root = root
            self.root.title("Power Efficiency Theory Simulator 17.0 | BitcoinVersus.Tech")
            self.root.geometry("1480x920")
            self.root.configure(bg="#0b1020")

            self.inputs = SimulationInputs()
            self.data = build_price_series(self.inputs)
            self.monte_carlo = build_monte_carlo_overlay(self.data)
            self.scenario_matrix = run_scenario_matrix(self.inputs, iterations=250)

            self.colors = {
                "bg": "#0b1020",
                "panel": "#111831",
                "panel_alt": "#182241",
                "text": "#eff3ff",
                "muted": "#a9b6d3",
                "accent": "#7bd7ff",
                "good": "#3ee6b0",
                "warn": "#ffcc66",
                "line": "#67e8f9",
                "band": "#1d4ed8",
                "scenario": "#f472b6",
            }

            self._build_ui()
            self.refresh_outputs()

        def _build_ui(self) -> None:
            shell = tk.Frame(self.root, bg=self.colors["bg"])
            shell.pack(fill="both", expand=True, padx=14, pady=14)

            self.sidebar = ScrollableSidebar(shell, bg=self.colors["panel"], width=430)
            self.sidebar.pack(side="left", fill="y", padx=(0, 14))

            main = tk.Frame(shell, bg=self.colors["bg"])
            main.pack(side="right", fill="both", expand=True)

            header = tk.Frame(main, bg=self.colors["panel"])
            header.pack(fill="x", pady=(0, 12))
            tk.Label(header, text="Power Efficiency Theory Simulator 17.0", font=("Helvetica", 20, "bold"), fg=self.colors["text"], bg=self.colors["panel"]).pack(anchor="w", padx=18, pady=(16, 2))
            tk.Label(header, text="Scenario matrix + network regime Monte Carlo integration", font=("Helvetica", 11), fg=self.colors["muted"], bg=self.colors["panel"]).pack(anchor="w", padx=18, pady=(0, 16))

            if Figure is None:
                self.chart_frame = tk.Frame(main, bg=self.colors["panel_alt"], height=420)
                self.chart_frame.pack(fill="both", expand=True)
                tk.Label(self.chart_frame, text="Matplotlib unavailable.", fg=self.colors["text"], bg=self.colors["panel_alt"]).pack(pady=40)
                return

            self.figure = Figure(figsize=(10, 6), dpi=100)
            self.ax = self.figure.add_subplot(111)
            self.canvas = FigureCanvasTkAgg(self.figure, master=main)
            self.canvas.get_tk_widget().pack(fill="both", expand=True)

            self.summary = tk.Text(main, height=13, bg=self.colors["panel"], fg=self.colors["text"], wrap="word", relief="flat")
            self.summary.pack(fill="x", pady=(12, 0))

        def refresh_outputs(self) -> None:
            self.data = build_price_series(self.inputs)
            self.monte_carlo = build_monte_carlo_overlay(self.data)
            self.scenario_matrix = run_scenario_matrix(self.inputs, iterations=250)
            summary_text = build_summary_text(self.scenario_matrix)
            if hasattr(self, "summary"):
                self.summary.delete("1.0", "end")
                self.summary.insert("1.0", summary_text)
            if hasattr(self, "ax"):
                self.ax.clear()
                years = self.data["years"]
                self.ax.plot(years, self.data["values_m"], color=self.colors["line"], linewidth=2.4, label="Base value ($M)")
                self.ax.fill_between(
                    years,
                    [v / 1e6 for v in self.monte_carlo["p10"]],
                    [v / 1e6 for v in self.monte_carlo["p90"]],
                    color=self.colors["band"],
                    alpha=0.18,
                    label="Monte Carlo p10-p90",
                )
                self.ax.set_facecolor(self.colors["panel_alt"])
                self.figure.patch.set_facecolor(self.colors["bg"])
                self.ax.set_title("Power Efficiency Theory 17.0")
                self.ax.set_xlabel("Year")
                self.ax.set_ylabel("Value ($ millions)")
                self.ax.grid(alpha=0.18)
                self.ax.legend()
                self.canvas.draw_idle()

    def launch_gui() -> None:
        root = tk.Tk()
        PowerEfficiencySimulator(root)
        root.mainloop()
else:
    def launch_gui() -> None:
        result = run_headless_validation(iterations=250)
        print(result["summary_text"])
        print(json.dumps(result, indent=2))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Power Efficiency Theory Simulator 17.0")
    parser.add_argument("--validate", action="store_true", help="Run headless validation and exit")
    parser.add_argument("--iterations", type=int, default=250, help="Monte Carlo iterations for validation")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.validate:
        result = run_headless_validation(iterations=args.iterations)
        print(result["summary_text"])
        print(json.dumps(result, indent=2))
        return 0

    launch_gui()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
