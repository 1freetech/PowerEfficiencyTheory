"""Power Efficiency Theory Simulator 17.0

Substantive maintenance update:
- keeps 17.0 as the current simulator instead of creating an empty version bump
- replaces pointwise chart noise with pathwise Monte Carlo compounding
- exposes power, efficiency, combined PEI, and lag components explicitly
- adds usable GUI controls plus an optional observed-market benchmark
- improves the chart into a professional value panel + PEI-driver panel
- makes the network-regime simulation use local RNG state and applies lag once per year
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


GUI_IMPORT_ERROR: str | None = None
try:
    import tkinter as tk
    from tkinter import messagebox

    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    from matplotlib.ticker import FuncFormatter

    GUI_AVAILABLE = True
except Exception as exc:  # pragma: no cover - environment dependent
    GUI_AVAILABLE = False
    GUI_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
    tk = None
    messagebox = None
    FigureCanvasTkAgg = None
    Figure = None
    FuncFormatter = None


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
    if not 0.0 <= q <= 1.0:
        raise ValueError("Percentile must be between 0 and 1.")
    if len(sorted_values) == 1:
        return float(sorted_values[0])

    position = (len(sorted_values) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = position - lower
    return float(sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight)


def validate_simulation_inputs(inputs: SimulationInputs) -> None:
    if inputs.start_value <= 0:
        raise ValueError("Start value must be greater than zero.")
    if inputs.end_year <= inputs.start_year:
        raise ValueError("End year must be greater than start year.")
    if inputs.power_growth <= -1.0:
        raise ValueError("Power growth must stay above -100%.")
    if not 0.0 <= inputs.efficiency_improvement < 0.95:
        raise ValueError("Efficiency improvement must be between 0% and 95%.")
    if not 0.0 <= inputs.lag_start < 1.0:
        raise ValueError("Initial lag must be between 0% and 100%.")
    if not 0.0 <= inputs.lag_decay < 1.0:
        raise ValueError("Lag decay must be between 0% and 100%.")


def build_price_series(inputs: SimulationInputs) -> dict:
    """Build deterministic PEI value and its component multipliers."""
    validate_simulation_inputs(inputs)

    years = list(range(inputs.start_year, inputs.end_year + 1))
    power_multiplier: list[float] = []
    efficiency_multiplier: list[float] = []
    pei_multiplier: list[float] = []
    lag_factor: list[float] = []
    unlagged_values: list[float] = []
    values: list[float] = []

    for year in years:
        x = year - inputs.start_year
        power = (1.0 + inputs.power_growth) ** x
        efficiency = (1.0 / (1.0 - inputs.efficiency_improvement)) ** x
        combined = power * efficiency
        lag = 1.0 - inputs.lag_start * ((1.0 - inputs.lag_decay) ** x)
        unlagged = inputs.start_value * combined
        value = unlagged * lag

        power_multiplier.append(power)
        efficiency_multiplier.append(efficiency)
        pei_multiplier.append(combined)
        lag_factor.append(lag)
        unlagged_values.append(unlagged)
        values.append(value)

    return {
        "years": years,
        "raw_values": values,
        "values_m": [value / 1e6 for value in values],
        "unlagged_values": unlagged_values,
        "unlagged_values_m": [value / 1e6 for value in unlagged_values],
        "power_multiplier": power_multiplier,
        "efficiency_multiplier": efficiency_multiplier,
        "pei_multiplier": pei_multiplier,
        "lag_factor": lag_factor,
        "growth_ratio": (1.0 + inputs.power_growth) / (1.0 - inputs.efficiency_improvement),
    }


def build_monte_carlo_overlay(
    inputs: SimulationInputs,
    iterations: int = 1000,
    seed: int = 42,
) -> dict:
    """Simulate pathwise PEI uncertainty so dispersion compounds through time."""
    validate_simulation_inputs(inputs)
    if iterations < 25:
        raise ValueError("Monte Carlo iterations must be at least 25.")

    rng = random.Random(seed)
    years = list(range(inputs.start_year, inputs.end_year + 1))
    p_std = max(0.01, abs(inputs.power_growth) * 0.20)
    e_std = max(0.008, abs(inputs.efficiency_improvement) * 0.20)
    lag_decay_std = max(0.01, inputs.lag_decay * 0.15)

    samples: list[list[float]] = []
    for _ in range(iterations):
        power = 1.0
        efficiency = 1.0
        path: list[float] = []
        path_lag_decay = max(0.0, min(0.95, rng.gauss(inputs.lag_decay, lag_decay_std)))

        for year in years:
            x = year - inputs.start_year
            if x > 0:
                p_draw = max(-0.95, min(0.80, rng.gauss(inputs.power_growth, p_std)))
                e_draw = max(0.0, min(0.75, rng.gauss(inputs.efficiency_improvement, e_std)))
                power *= 1.0 + p_draw
                efficiency *= 1.0 / (1.0 - e_draw)

            lag = 1.0 - inputs.lag_start * ((1.0 - path_lag_decay) ** x)
            path.append(inputs.start_value * power * efficiency * lag)

        samples.append(path)

    p10: list[float] = []
    p50: list[float] = []
    p90: list[float] = []
    for index in range(len(years)):
        column = sorted(path[index] for path in samples)
        p10.append(_percentile(column, 0.10))
        p50.append(_percentile(column, 0.50))
        p90.append(_percentile(column, 0.90))

    return {
        "years": years,
        "iterations": iterations,
        "method": "pathwise_compounded_parameter_uncertainty",
        "p10": p10,
        "p50": p50,
        "p90": p90,
    }


def build_default_scenarios(inputs: SimulationInputs) -> list[ScenarioDefinition]:
    validate_simulation_inputs(inputs)
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
            lag_start=min(inputs.lag_start + 0.08, 0.95),
            lag_decay=max(inputs.lag_decay - 0.03, 0.01),
        ),
        ScenarioDefinition(
            name="accelerated",
            power_growth=inputs.power_growth + 0.05,
            efficiency_improvement=min(inputs.efficiency_improvement + 0.02, 0.90),
            lag_start=max(inputs.lag_start - 0.08, 0.0),
            lag_decay=min(inputs.lag_decay + 0.03, 0.95),
        ),
    ]


class NetworkRegimeSimulator:
    """Directional network/mining-economics overlay, not a full miner P&L model."""

    def __init__(self, inputs: NetworkInputs | None = None) -> None:
        self.inputs = inputs or NetworkInputs()
        if self.inputs.iterations < 25:
            raise ValueError("Network-regime iterations must be at least 25.")
        if self.inputs.years < 1:
            raise ValueError("Network-regime years must be positive.")
        self.rng = random.Random(self.inputs.random_seed)

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def _draw(self, mean: float, std: float, low: float, high: float) -> float:
        return self._clamp(self.rng.gauss(mean, std), low, high)

    def _run_path(self) -> list[dict]:
        power_multiplier = 1.0
        efficiency_multiplier = 1.0
        difficulty_multiplier = 1.0
        fee_multiplier = 1.0
        energy_multiplier = 1.0
        points: list[dict] = []

        for year in range(self.inputs.years + 1):
            if year == 0:
                power_growth = self.inputs.power_growth_mean
                efficiency_improvement = self.inputs.efficiency_improvement_mean
                difficulty_growth = self.inputs.difficulty_growth_mean
                fee_pressure = self.inputs.fee_pressure_mean
                energy_price = self.inputs.energy_price_mean
            else:
                power_growth = self._draw(self.inputs.power_growth_mean, self.inputs.power_growth_std, -0.20, 0.60)
                efficiency_improvement = self._draw(
                    self.inputs.efficiency_improvement_mean,
                    self.inputs.efficiency_improvement_std,
                    0.0,
                    0.40,
                )
                difficulty_growth = self._draw(
                    self.inputs.difficulty_growth_mean,
                    self.inputs.difficulty_growth_std,
                    -0.05,
                    0.40,
                )
                fee_pressure = self._draw(self.inputs.fee_pressure_mean, self.inputs.fee_pressure_std, -0.05, 0.20)
                energy_price = self._draw(self.inputs.energy_price_mean, self.inputs.energy_price_std, 0.01, 0.25)

                power_multiplier *= 1.0 + power_growth
                efficiency_multiplier *= 1.0 / (1.0 - efficiency_improvement)
                difficulty_multiplier *= 1.0 / (1.0 + difficulty_growth)
                fee_multiplier *= 1.0 + fee_pressure
                # Directional pressure proxy: higher $/kWh suppresses the modeled value path.
                energy_multiplier *= 1.0 / (1.0 + energy_price * 4.0)

            lag = 1.0 - self.inputs.lag_start * ((1.0 - self.inputs.lag_decay) ** year)
            current_value = (
                self.inputs.start_value
                * power_multiplier
                * efficiency_multiplier
                * difficulty_multiplier
                * fee_multiplier
                * energy_multiplier
                * lag
            )
            resilience_score = (
                (1.0 + power_growth)
                * (1.0 / max(1e-9, 1.0 - efficiency_improvement))
                * (1.0 + fee_pressure)
                / max(1e-9, (1.0 + difficulty_growth) * (1.0 + energy_price))
            )

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
            "method": "directional_network_regime_proxy",
            "summary": {
                "p10_final_value": _percentile(finals, 0.10),
                "p50_final_value": _percentile(finals, 0.50),
                "p90_final_value": _percentile(finals, 0.90),
                "mean_final_value": statistics.fmean(finals),
                "mean_resilience_score": statistics.fmean(resilience),
            },
        }


def build_network_inputs_for_scenario(
    scenario_inputs: SimulationInputs,
    iterations: int,
    seed: int,
) -> NetworkInputs:
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
            scenario_inputs,
            iterations=iterations,
            seed=42 + idx,
        )
        network = NetworkRegimeSimulator(
            build_network_inputs_for_scenario(
                scenario_inputs,
                iterations=max(250, iterations * 2),
                seed=84 + idx,
            )
        ).run()
        matrix.append(
            {
                "name": scenario.name,
                "inputs": asdict(scenario_inputs),
                "growth_ratio": float(series["growth_ratio"]),
                "final_pei_multiplier": float(series["pei_multiplier"][-1]),
                "final_lag_factor": float(series["lag_factor"][-1]),
                "final_value": float(series["raw_values"][-1]),
                "unlagged_final_value": float(series["unlagged_values"][-1]),
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
        "Power Efficiency Theory 17.0 analytical summary",
        (
            f"Top lag-adjusted case: {leader['name']} -> ${leader['final_value']:,.0f} "
            f"| PEI {leader['final_pei_multiplier']:.2f}x | Monte Carlo P50 ${leader['p50_final']:,.0f} "
            f"| network proxy P50 ${leader['network_regime']['summary']['p50_final_value']:,.0f}"
        ),
        (
            f"Lowest lag-adjusted case: {trailer['name']} -> ${trailer['final_value']:,.0f} "
            f"| PEI {trailer['final_pei_multiplier']:.2f}x | Monte Carlo P50 ${trailer['p50_final']:,.0f} "
            f"| network proxy P50 ${trailer['network_regime']['summary']['p50_final_value']:,.0f}"
        ),
        "Scenario table:",
    ]
    for item in ranked:
        net = item["network_regime"]["summary"]
        lines.append(
            "- {name}: PEI={pei:.2f}x, lag={lag:.3f}, unlagged=${unlagged:,.0f}, "
            "lag_adjusted=${final:,.0f}, MC P10/P50/P90=${p10:,.0f}/${p50:,.0f}/${p90:,.0f}, "
            "network P50=${np50:,.0f}, resilience_proxy={resilience:.4f}".format(
                name=item["name"],
                pei=item["final_pei_multiplier"],
                lag=item["final_lag_factor"],
                unlagged=item["unlagged_final_value"],
                final=item["final_value"],
                p10=item["p10_final"],
                p50=item["p50_final"],
                p90=item["p90_final"],
                np50=net["p50_final_value"],
                resilience=net["mean_resilience_score"],
            )
        )
    return "\n".join(lines)


def run_headless_validation(iterations: int = 1000) -> dict:
    inputs = SimulationInputs()
    series = build_price_series(inputs)
    overlay = build_monte_carlo_overlay(inputs, iterations=iterations)
    matrix = run_scenario_matrix(inputs, iterations=iterations)
    summary_text = build_summary_text(matrix)

    result = {
        "version": "17.0",
        "model_role": "research_scenario_model_not_price_forecast",
        "inputs": asdict(inputs),
        "deterministic": {
            "growth_ratio": float(series["growth_ratio"]),
            "final_pei_multiplier": float(series["pei_multiplier"][-1]),
            "final_lag_factor": float(series["lag_factor"][-1]),
            "unlagged_final_value": float(series["unlagged_values"][-1]),
            "lag_adjusted_final_value": float(series["raw_values"][-1]),
        },
        "monte_carlo": {
            "iterations": iterations,
            "method": overlay["method"],
            "p10_final": float(overlay["p10"][-1]),
            "p50_final": float(overlay["p50"][-1]),
            "p90_final": float(overlay["p90"][-1]),
        },
        "scenario_matrix": matrix,
        "summary_text": summary_text,
        "gui_available": GUI_AVAILABLE,
        "gui_import_error": GUI_IMPORT_ERROR,
    }

    Path("power_efficiency_17_0_validation.json").write_text(
        json.dumps(result, indent=2),
        encoding="utf-8",
    )
    Path("power_efficiency_17_0_summary.txt").write_text(summary_text + "\n", encoding="utf-8")
    return result


if GUI_AVAILABLE:
    class ScrollableSidebar(tk.Frame):
        def __init__(self, parent: tk.Widget, bg: str, width: int = 430) -> None:
            super().__init__(parent, bg=bg, width=width)
            self.pack_propagate(False)
            self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0, width=width)
            self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
            self.inner = tk.Frame(self.canvas, bg=bg)
            self.inner.bind(
                "<Configure>",
                lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
            )
            self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
            self.canvas.configure(yscrollcommand=self.scrollbar.set)
            self.canvas.bind(
                "<Configure>",
                lambda e: self.canvas.itemconfigure(self.window_id, width=e.width),
            )
            self.canvas.pack(side="left", fill="both", expand=True)
            self.scrollbar.pack(side="right", fill="y")
            self.canvas.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
            self.canvas.bind_all("<Button-4>", self._on_linux_wheel, add="+")
            self.canvas.bind_all("<Button-5>", self._on_linux_wheel, add="+")

        def _pointer_inside(self) -> bool:
            x_root, y_root = self.winfo_pointerxy()
            widget = self.winfo_containing(x_root, y_root)
            while widget is not None:
                if widget is self:
                    return True
                widget = widget.master
            return False

        def _on_mousewheel(self, event: tk.Event) -> None:
            if self._pointer_inside():
                self.canvas.yview_scroll(int(-event.delta / 120), "units")

        def _on_linux_wheel(self, event: tk.Event) -> None:
            if not self._pointer_inside():
                return
            self.canvas.yview_scroll(-1 if event.num == 4 else 1, "units")


    class PowerEfficiencySimulator:
        def __init__(self, root: tk.Tk) -> None:
            self.root = root
            self.root.title("Power Efficiency Theory Simulator 17.0 | BitcoinVersus.Tech")
            self.root.geometry("1560x980")
            self.root.minsize(1240, 780)

            self.colors = {
                "bg": "#050505",
                "panel": "#0b0b0b",
                "panel_alt": "#111111",
                "text": "#f4f4f4",
                "muted": "#a5a5a5",
                "green": "#39ff14",
                "white": "#f4f4f4",
                "amber": "#ffb347",
                "cyan": "#67e8f9",
                "band": "#2b6cb0",
                "red": "#ff6b6b",
            }
            self.root.configure(bg=self.colors["bg"])

            self.inputs = SimulationInputs()
            self.iterations = 1000
            self.benchmark_year: int | None = None
            self.benchmark_value: float | None = None
            self.vars: dict[str, tk.StringVar] = {}

            self._build_ui()
            self._set_defaults()
            self.refresh_outputs()

        def _build_ui(self) -> None:
            shell = tk.Frame(self.root, bg=self.colors["bg"])
            shell.pack(fill="both", expand=True, padx=12, pady=12)

            self.sidebar = ScrollableSidebar(shell, bg=self.colors["panel"], width=390)
            self.sidebar.pack(side="left", fill="y", padx=(0, 12))

            main = tk.Frame(shell, bg=self.colors["bg"])
            main.pack(side="right", fill="both", expand=True)

            self._build_controls(self.sidebar.inner)

            header = tk.Frame(main, bg=self.colors["panel"])
            header.pack(fill="x", pady=(0, 10))
            tk.Label(
                header,
                text="Power Efficiency Theory",
                font=("Segoe UI", 20, "bold"),
                fg=self.colors["green"],
                bg=self.colors["panel"],
            ).pack(anchor="w", padx=16, pady=(12, 0))
            tk.Label(
                header,
                text="Value projection, uncertainty band, and PEI driver decomposition",
                font=("Segoe UI", 10),
                fg=self.colors["muted"],
                bg=self.colors["panel"],
            ).pack(anchor="w", padx=16, pady=(2, 12))

            self.figure = Figure(figsize=(10.8, 7.0), dpi=100, facecolor=self.colors["bg"])
            self.ax_value = self.figure.add_subplot(211)
            self.ax_drivers = self.figure.add_subplot(212)
            self.figure.subplots_adjust(left=0.09, right=0.94, top=0.94, bottom=0.09, hspace=0.30)

            self.canvas = FigureCanvasTkAgg(self.figure, master=main)
            self.canvas.get_tk_widget().pack(fill="both", expand=True)

            self.summary = tk.Text(
                main,
                height=8,
                bg=self.colors["panel"],
                fg=self.colors["text"],
                insertbackground=self.colors["green"],
                wrap="word",
                relief="flat",
                padx=10,
                pady=8,
                font=("Consolas", 9),
            )
            self.summary.pack(fill="x", pady=(10, 0))

        def _build_controls(self, parent: tk.Widget) -> None:
            tk.Label(
                parent,
                text="MODEL INPUTS",
                fg=self.colors["green"],
                bg=self.colors["panel"],
                font=("Segoe UI", 12, "bold"),
            ).pack(anchor="w", padx=14, pady=(16, 8))

            fields = [
                ("Start value ($)", "start_value"),
                ("Power growth (%)", "power_growth"),
                ("Efficiency gain (%)", "efficiency_improvement"),
                ("Initial lag (%)", "lag_start"),
                ("Lag decay (%)", "lag_decay"),
                ("Start year", "start_year"),
                ("End year", "end_year"),
                ("Monte Carlo paths", "iterations"),
            ]
            for label, key in fields:
                row = tk.Frame(parent, bg=self.colors["panel"])
                row.pack(fill="x", padx=14, pady=4)
                tk.Label(
                    row,
                    text=label,
                    width=20,
                    anchor="w",
                    fg=self.colors["text"],
                    bg=self.colors["panel"],
                    font=("Segoe UI", 9),
                ).pack(side="left")
                var = tk.StringVar()
                tk.Entry(
                    row,
                    textvariable=var,
                    width=16,
                    bg=self.colors["panel_alt"],
                    fg=self.colors["green"],
                    insertbackground=self.colors["green"],
                    relief="flat",
                ).pack(side="right", ipady=4)
                self.vars[key] = var

            tk.Label(
                parent,
                text="OPTIONAL OBSERVED BENCHMARK",
                fg=self.colors["green"],
                bg=self.colors["panel"],
                font=("Segoe UI", 10, "bold"),
            ).pack(anchor="w", padx=14, pady=(18, 8))

            for label, key in [
                ("Benchmark year", "benchmark_year"),
                ("Observed value ($)", "benchmark_value"),
            ]:
                row = tk.Frame(parent, bg=self.colors["panel"])
                row.pack(fill="x", padx=14, pady=4)
                tk.Label(
                    row,
                    text=label,
                    width=20,
                    anchor="w",
                    fg=self.colors["text"],
                    bg=self.colors["panel"],
                    font=("Segoe UI", 9),
                ).pack(side="left")
                var = tk.StringVar()
                tk.Entry(
                    row,
                    textvariable=var,
                    width=16,
                    bg=self.colors["panel_alt"],
                    fg=self.colors["green"],
                    insertbackground=self.colors["green"],
                    relief="flat",
                ).pack(side="right", ipady=4)
                self.vars[key] = var

            buttons = tk.Frame(parent, bg=self.colors["panel"])
            buttons.pack(fill="x", padx=14, pady=(16, 8))
            tk.Button(
                buttons,
                text="Run model",
                command=self.apply_inputs,
                bg=self.colors["green"],
                fg="#000000",
                activebackground="#7dff63",
                relief="flat",
                font=("Segoe UI", 9, "bold"),
                padx=12,
                pady=6,
            ).pack(side="left")
            tk.Button(
                buttons,
                text="Reset",
                command=self._reset_and_refresh,
                bg=self.colors["panel_alt"],
                fg=self.colors["white"],
                activeforeground=self.colors["green"],
                relief="flat",
                padx=12,
                pady=6,
            ).pack(side="left", padx=(8, 0))

            note = (
                "PEI combines performance growth and energy-efficiency improvement. "
                "The lag term is a convergence assumption. The Monte Carlo and network-regime "
                "layers are research scenario tools, not a price forecast or miner P&L."
            )
            tk.Label(
                parent,
                text=note,
                fg=self.colors["muted"],
                bg=self.colors["panel"],
                justify="left",
                wraplength=345,
                font=("Segoe UI", 9),
            ).pack(anchor="w", padx=14, pady=(12, 18))

        def _set_defaults(self) -> None:
            defaults = {
                "start_value": "75000",
                "power_growth": "15",
                "efficiency_improvement": "7",
                "lag_start": "50",
                "lag_decay": "15",
                "start_year": "2025",
                "end_year": "2040",
                "iterations": "1000",
                "benchmark_year": "",
                "benchmark_value": "",
            }
            for key, value in defaults.items():
                self.vars[key].set(value)

        def _reset_and_refresh(self) -> None:
            self._set_defaults()
            self.apply_inputs()

        def apply_inputs(self) -> None:
            try:
                candidate = SimulationInputs(
                    start_value=float(self.vars["start_value"].get()),
                    power_growth=float(self.vars["power_growth"].get()) / 100.0,
                    efficiency_improvement=float(self.vars["efficiency_improvement"].get()) / 100.0,
                    lag_start=float(self.vars["lag_start"].get()) / 100.0,
                    lag_decay=float(self.vars["lag_decay"].get()) / 100.0,
                    start_year=int(self.vars["start_year"].get()),
                    end_year=int(self.vars["end_year"].get()),
                )
                validate_simulation_inputs(candidate)
                iterations = int(self.vars["iterations"].get())
                if iterations < 25 or iterations > 50000:
                    raise ValueError("Monte Carlo paths must be between 25 and 50,000.")

                benchmark_year_text = self.vars["benchmark_year"].get().strip()
                benchmark_value_text = self.vars["benchmark_value"].get().strip()
                benchmark_year = int(benchmark_year_text) if benchmark_year_text else None
                benchmark_value = float(benchmark_value_text) if benchmark_value_text else None
                if (benchmark_year is None) != (benchmark_value is None):
                    raise ValueError("Enter both benchmark year and observed value, or leave both blank.")
                if benchmark_value is not None and benchmark_value <= 0:
                    raise ValueError("Observed benchmark value must be greater than zero.")

                self.inputs = candidate
                self.iterations = iterations
                self.benchmark_year = benchmark_year
                self.benchmark_value = benchmark_value
                self.refresh_outputs()
            except Exception as exc:
                messagebox.showerror("Invalid input", str(exc))

        def refresh_outputs(self) -> None:
            self.data = build_price_series(self.inputs)
            self.monte_carlo = build_monte_carlo_overlay(
                self.inputs,
                iterations=self.iterations,
                seed=42,
            )
            self.scenario_matrix = run_scenario_matrix(
                self.inputs,
                iterations=min(self.iterations, 3000),
            )
            self._draw_chart()
            self._draw_summary()

        def _format_millions(self, value: float, _pos: int) -> str:
            return f"${value:,.1f}M" if abs(value) < 1000 else f"${value / 1000:,.1f}B"

        def _style_axis(self, ax) -> None:
            ax.set_facecolor(self.colors["panel_alt"])
            ax.tick_params(colors=self.colors["muted"])
            ax.xaxis.label.set_color(self.colors["text"])
            ax.yaxis.label.set_color(self.colors["text"])
            ax.title.set_color(self.colors["text"])
            for spine in ax.spines.values():
                spine.set_color("#333333")
            ax.grid(alpha=0.14, color=self.colors["white"])

        def _draw_chart(self) -> None:
            years = self.data["years"]
            deterministic_m = self.data["values_m"]
            unlagged_m = self.data["unlagged_values_m"]
            p10_m = [v / 1e6 for v in self.monte_carlo["p10"]]
            p50_m = [v / 1e6 for v in self.monte_carlo["p50"]]
            p90_m = [v / 1e6 for v in self.monte_carlo["p90"]]

            self.ax_value.clear()
            self.ax_drivers.clear()
            self.figure.patch.set_facecolor(self.colors["bg"])

            self.ax_value.fill_between(
                years,
                p10_m,
                p90_m,
                color=self.colors["band"],
                alpha=0.20,
                label="Pathwise Monte Carlo P10–P90",
            )
            self.ax_value.plot(
                years,
                p50_m,
                color=self.colors["cyan"],
                linewidth=1.8,
                linestyle=":",
                label="Monte Carlo P50",
            )
            self.ax_value.plot(
                years,
                unlagged_m,
                color=self.colors["white"],
                linewidth=1.8,
                linestyle="--",
                label="Unlagged PEI value",
            )
            self.ax_value.plot(
                years,
                deterministic_m,
                color=self.colors["green"],
                linewidth=2.8,
                label="Lag-adjusted PEI value",
            )
            self.ax_value.fill_between(
                years,
                deterministic_m,
                unlagged_m,
                color=self.colors["green"],
                alpha=0.06,
                label="Lag / convergence gap",
            )

            if self.benchmark_year is not None and self.benchmark_value is not None:
                self.ax_value.scatter(
                    [self.benchmark_year],
                    [self.benchmark_value / 1e6],
                    s=75,
                    edgecolors=self.colors["green"],
                    facecolors=self.colors["bg"],
                    linewidths=2.0,
                    zorder=5,
                    label="Observed benchmark",
                )

            self.ax_value.set_title("PEI value projection and uncertainty")
            self.ax_value.set_xlabel("Year")
            self.ax_value.set_ylabel("Modeled value")
            self.ax_value.yaxis.set_major_formatter(FuncFormatter(self._format_millions))
            self._style_axis(self.ax_value)
            legend = self.ax_value.legend(
                loc="upper left",
                facecolor=self.colors["panel"],
                edgecolor="#333333",
                fontsize=8,
            )
            for text in legend.get_texts():
                text.set_color(self.colors["text"])

            self.ax_drivers.plot(
                years,
                self.data["power_multiplier"],
                color=self.colors["amber"],
                linewidth=2.0,
                label="Power multiplier",
            )
            self.ax_drivers.plot(
                years,
                self.data["efficiency_multiplier"],
                color=self.colors["cyan"],
                linewidth=2.0,
                label="Efficiency multiplier",
            )
            self.ax_drivers.plot(
                years,
                self.data["pei_multiplier"],
                color=self.colors["green"],
                linewidth=2.6,
                label="Combined PEI multiplier",
            )
            self.ax_drivers.set_title("PEI driver decomposition")
            self.ax_drivers.set_xlabel("Year")
            self.ax_drivers.set_ylabel("Multiplier (×)")
            self._style_axis(self.ax_drivers)

            lag_axis = self.ax_drivers.twinx()
            lag_axis.plot(
                years,
                self.data["lag_factor"],
                color=self.colors["white"],
                linewidth=1.4,
                linestyle="--",
                alpha=0.70,
                label="Lag factor",
            )
            lag_axis.set_ylabel("Lag factor", color=self.colors["muted"])
            lag_axis.tick_params(colors=self.colors["muted"])
            lag_axis.set_ylim(0.0, 1.05)
            for spine in lag_axis.spines.values():
                spine.set_color("#333333")

            lines1, labels1 = self.ax_drivers.get_legend_handles_labels()
            lines2, labels2 = lag_axis.get_legend_handles_labels()
            legend2 = self.ax_drivers.legend(
                lines1 + lines2,
                labels1 + labels2,
                loc="upper left",
                facecolor=self.colors["panel"],
                edgecolor="#333333",
                fontsize=8,
            )
            for text in legend2.get_texts():
                text.set_color(self.colors["text"])

            self.canvas.draw_idle()

        def _draw_summary(self) -> None:
            final_value = self.data["raw_values"][-1]
            final_unlagged = self.data["unlagged_values"][-1]
            pei = self.data["pei_multiplier"][-1]
            p10 = self.monte_carlo["p10"][-1]
            p50 = self.monte_carlo["p50"][-1]
            p90 = self.monte_carlo["p90"][-1]

            lines = [
                f"PEI multiplier: {pei:.3f}x",
                f"Unlagged PEI value: ${final_unlagged:,.0f}",
                f"Lag-adjusted PEI value: ${final_value:,.0f}",
                f"Pathwise Monte Carlo P10/P50/P90: ${p10:,.0f} / ${p50:,.0f} / ${p90:,.0f}",
            ]
            if self.benchmark_year is not None and self.benchmark_value is not None:
                if self.benchmark_year in self.data["years"]:
                    index = self.data["years"].index(self.benchmark_year)
                    model_value = self.data["raw_values"][index]
                    gap = model_value - self.benchmark_value
                    gap_pct = (gap / self.benchmark_value) * 100.0
                    lines.append(
                        f"Observed benchmark gap ({self.benchmark_year}): "
                        f"${gap:,.0f} ({gap_pct:+.1f}%) versus lag-adjusted PEI."
                    )
                else:
                    lines.append("Observed benchmark is outside the modeled year range.")

            lines.append("")
            lines.append("Research scenario model only; network-regime outputs are directional proxies, not a miner P&L or financial forecast.")

            self.summary.configure(state="normal")
            self.summary.delete("1.0", "end")
            self.summary.insert("1.0", "\n".join(lines))
            self.summary.configure(state="disabled")


    def launch_gui() -> None:
        root = tk.Tk()
        PowerEfficiencySimulator(root)
        root.mainloop()
else:
    def launch_gui() -> None:
        result = run_headless_validation(iterations=1000)
        print(result["summary_text"])
        print(json.dumps(result, indent=2))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Power Efficiency Theory Simulator 17.0")
    parser.add_argument("--validate", action="store_true", help="Run headless validation and exit")
    parser.add_argument("--iterations", type=int, default=1000, help="Monte Carlo paths for validation")
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
