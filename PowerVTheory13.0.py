"""Power Efficiency Theory Simulator 13.0

Additive upgrade goals:
- preserve the 7.0 headless-safe validation path
- add scenario support so multiple growth/efficiency regimes can be compared in one run
- produce a compact markdown-style summary that is useful even without GUI libraries
- avoid touching existing user-created files; publish as a new additive version only
"""

from __future__ import annotations

import argparse
import json
import random
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


def run_scenario_matrix(inputs: SimulationInputs, iterations: int) -> dict:
    scenarios = build_default_scenarios(inputs)
    matrix: list[dict] = []
    for scenario in scenarios:
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
            seed=42 + len(matrix),
        )
        matrix.append(
            {
                "name": scenario.name,
                "inputs": asdict(scenario_inputs),
                "growth_ratio": float(series["growth_ratio"]),
                "final_value": float(series["raw_values"][-1]),
                "p10_final": float(overlay["p10"][-1]),
                "p50_final": float(overlay["p50"][-1]),
                "p90_final": float(overlay["p90"][-1]),
            }
        )
    return {"scenarios": matrix}


def build_summary_text(matrix: dict) -> str:
    scenarios = matrix["scenarios"]
    ranked = sorted(scenarios, key=lambda item: item["final_value"], reverse=True)
    leader = ranked[0]
    trailer = ranked[-1]
    lines = [
        "Power Efficiency Theory 13.0 scenario summary",
        f"Top case: {leader['name']} -> final deterministic value ${leader['final_value']:,.0f} | P50 ${leader['p50_final']:,.0f}",
        f"Lowest case: {trailer['name']} -> final deterministic value ${trailer['final_value']:,.0f} | P50 ${trailer['p50_final']:,.0f}",
        "Scenario table:",
    ]
    for item in ranked:
        lines.append(
            "- {name}: growth_ratio={growth_ratio:.4f}, final=${final_value:,.0f}, p10=${p10_final:,.0f}, p50=${p50_final:,.0f}, p90=${p90_final:,.0f}".format(
                **item
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
        "version": "8.0",
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

    Path("power_efficiency_13_0_validation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    Path("power_efficiency_13_0_summary.txt").write_text(summary_text + "\n", encoding="utf-8")
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
            self.root.title("Power Efficiency Theory Simulator 13.0 | BitcoinVersus.Tech")
            self.root.geometry("1480x920")
            self.root.configure(bg="#050505")
            self.bg = "#050505"
            self.panel = "#0b0b0b"
            self.panel_2 = "#101010"
            self.neon = "#39ff14"
            self.muted = "#9cff8a"
            self.default_line = "#00ff37"
            self.monte_color = "#00e5ff"
            self.inputs: dict[str, tk.StringVar] = {}
            self.monte_enabled = tk.BooleanVar(value=True)
            self.monte_iterations = tk.StringVar(value="250")
            self.results_text = tk.StringVar(value="Run a simulation to generate a chart explanation here.")
            self._build_layout()
            self._build_chart()
            self._set_defaults()
            self.calculate()

        def _build_layout(self) -> None:
            self.root.grid_columnconfigure(0, weight=0)
            self.root.grid_columnconfigure(1, weight=1)
            self.root.grid_rowconfigure(0, weight=1)
            self.sidebar = ScrollableSidebar(self.root, bg=self.bg, width=420)
            self.sidebar.grid(row=0, column=0, sticky="nsw")
            self.control_frame = self.sidebar.inner
            self.chart_shell = tk.Frame(self.root, bg=self.bg, padx=12, pady=12)
            self.chart_shell.grid(row=0, column=1, sticky="nsew")
            self.chart_shell.grid_columnconfigure(0, weight=1)
            self.chart_shell.grid_rowconfigure(0, weight=1)
            self._build_controls()

        def _build_controls(self) -> None:
            fields = [("Start Value V0", "start_value"), ("Power Growth p", "power_growth"), ("Efficiency Improvement e", "efficiency_improvement"), ("Initial Lag L", "lag_start"), ("Lag Decay d", "lag_decay"), ("Start Year", "start_year"), ("End Year", "end_year")]
            for label_text, key in fields:
                row = tk.Frame(self.control_frame, bg=self.bg)
                row.pack(fill="x", pady=4, padx=14)
                tk.Label(row, text=label_text, bg=self.bg, fg=self.neon, width=20, anchor="w").pack(side="left")
                var = tk.StringVar()
                tk.Entry(row, textvariable=var, bg=self.panel_2, fg=self.neon, insertbackground=self.neon, width=20).pack(side="left")
                self.inputs[key] = var
            monte_row = tk.Frame(self.control_frame, bg=self.bg)
            monte_row.pack(fill="x", pady=8, padx=14)
            tk.Checkbutton(monte_row, text="Enable Monte Carlo", variable=self.monte_enabled, bg=self.bg, fg=self.neon, selectcolor=self.panel_2).pack(side="left")
            tk.Entry(monte_row, textvariable=self.monte_iterations, bg=self.panel_2, fg=self.neon, insertbackground=self.neon, width=10).pack(side="left", padx=(8, 0))
            button_row = tk.Frame(self.control_frame, bg=self.bg)
            button_row.pack(fill="x", pady=10, padx=14)
            tk.Button(button_row, text="Calculate", command=self.calculate, bg=self.neon, fg="#000000").pack(side="left")
            tk.Button(button_row, text="Save Validation", command=self.save_validation, bg=self.panel, fg=self.neon).pack(side="left", padx=(8, 0))
            tk.Label(self.control_frame, textvariable=self.results_text, bg=self.bg, fg=self.muted, justify="left", wraplength=360).pack(anchor="w", padx=14, pady=(10, 0))

        def _build_chart(self) -> None:
            self.figure = Figure(figsize=(8.4, 5.0), dpi=125, facecolor=self.panel)
            self.ax = self.figure.add_subplot(111)
            self.ax.set_facecolor(self.panel)
            self.canvas = FigureCanvasTkAgg(self.figure, master=self.chart_shell)
            self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        def _set_defaults(self) -> None:
            defaults = {"start_value": "75000", "power_growth": "0.15", "efficiency_improvement": "0.07", "lag_start": "0.50", "lag_decay": "0.15", "start_year": "2025", "end_year": "2040"}
            for key, value in defaults.items():
                self.inputs[key].set(value)

        def _collect_inputs(self) -> SimulationInputs:
            return SimulationInputs(start_value=float(self.inputs["start_value"].get()), power_growth=float(self.inputs["power_growth"].get()), efficiency_improvement=float(self.inputs["efficiency_improvement"].get()), lag_start=float(self.inputs["lag_start"].get()), lag_decay=float(self.inputs["lag_decay"].get()), start_year=int(self.inputs["start_year"].get()), end_year=int(self.inputs["end_year"].get()))

        def calculate(self) -> None:
            try:
                inputs = self._collect_inputs()
                series = build_price_series(inputs)
            except Exception as exc:
                messagebox.showerror("Invalid Input", str(exc))
                return
            self.ax.clear()
            self.ax.set_facecolor(self.panel)
            self.ax.plot(series["years"], series["values_m"], color=self.default_line, linewidth=2.8, label="Deterministic")
            summary = f"Final deterministic value: ${series['raw_values'][-1]:,.0f}. Growth ratio: {series['growth_ratio']:.4f}."
            if self.monte_enabled.get():
                overlay = build_monte_carlo_overlay(series, iterations=int(self.monte_iterations.get()))
                self.ax.plot(overlay["years"], [v / 1e6 for v in overlay["p50"]], color=self.monte_color, linewidth=2.2, linestyle="--", label="Monte Carlo P50")
                self.ax.fill_between(overlay["years"], [v / 1e6 for v in overlay["p10"]], [v / 1e6 for v in overlay["p90"]], color=self.monte_color, alpha=0.08, label="Monte Carlo Band")
                summary += f" Monte Carlo P50: ${overlay['p50'][-1]:,.0f}; P10: ${overlay['p10'][-1]:,.0f}; P90: ${overlay['p90'][-1]:,.0f}."
            matrix = run_scenario_matrix(inputs, iterations=max(10, int(self.monte_iterations.get())))
            summary += " " + build_summary_text(matrix).splitlines()[1]
            self.ax.set_title("Power Efficiency Theory 13.0", color=self.neon)
            self.ax.set_xlabel("Year", color=self.neon)
            self.ax.set_ylabel("Millions USD", color=self.neon)
            self.ax.tick_params(colors=self.neon)
            for spine in self.ax.spines.values():
                spine.set_color(self.neon)
            self.ax.grid(True, color=self.neon, alpha=0.10)
            legend = self.ax.legend(facecolor=self.panel, edgecolor=self.neon)
            for text in legend.get_texts():
                text.set_color(self.neon)
            self.canvas.draw_idle()
            self.results_text.set(summary)

        def save_validation(self) -> None:
            result = run_headless_validation(iterations=max(10, int(self.monte_iterations.get())))
            messagebox.showinfo("Validation Saved", f"Saved validation to power_efficiency_13_0_validation.json\nFinal value: ${result['final_value']:,.0f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Power Efficiency Theory Simulator 13.0")
    parser.add_argument("--validate", action="store_true", help="Run headless validation and exit")
    parser.add_argument("--iterations", type=int, default=250, help="Monte Carlo iterations for validation")
    args = parser.parse_args()

    if args.validate:
        result = run_headless_validation(iterations=args.iterations)
        print(json.dumps(result, indent=2))
        return

    if not (GUI_AVAILABLE and NUMPY_AVAILABLE):
        print("GUI launch unavailable in this environment.")
        print(f"GUI dependency status: {GUI_IMPORT_ERROR}")
        print(f"NumPy dependency status: {NUMPY_IMPORT_ERROR}")
        print("Run with --validate for a meaningful headless test.")
        sys.exit(0)

    root = tk.Tk()
    PowerEfficiencySimulator(root)
    root.mainloop()


if __name__ == "__main__":
    main()
