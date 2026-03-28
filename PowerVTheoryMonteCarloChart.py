import csv
import json
from pathlib import Path


BG = "#050505"
PANEL = "#0b0b0b"
NEON = "#39ff14"
MUTED = "#9cff8a"
P10_COLOR = "#f10101"
P50_COLOR = "#fd7e07"
P90_COLOR = "#00ff88"


def load_results(path: str = "power_efficiency_monte_carlo_results.json") -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def extract_series(results: dict):
    bearish = results["representative_paths"]["bearish_p10"]
    base = results["representative_paths"]["base_p50"]
    bullish = results["representative_paths"]["bullish_p90"]

    years = [point["year_index"] for point in base]
    p10 = [point["value"] for point in bearish]
    p50 = [point["value"] for point in base]
    p90 = [point["value"] for point in bullish]
    return years, p10, p50, p90


def write_csv(results: dict, output_path: str = "power_efficiency_monte_carlo_band.csv") -> str:
    years, p10, p50, p90 = extract_series(results)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["year_index", "p10_value", "p50_value", "p90_value"])
        for year, a, b, c in zip(years, p10, p50, p90):
            writer.writerow([year, a, b, c])
    return output_path


def write_text_summary(results: dict, output_path: str = "power_efficiency_monte_carlo_chart_summary.txt") -> str:
    summary = results["summary"]
    years, p10, p50, p90 = extract_series(results)
    lines = [
        "Power Efficiency Theory Monte Carlo Scenario Band",
        "",
        f"P10 final value: ${summary['p10_final_value']:,.2f}",
        f"P50 final value: ${summary['p50_final_value']:,.2f}",
        f"P90 final value: ${summary['p90_final_value']:,.2f}",
        f"Mean final value: ${summary['mean_final_value']:,.2f}",
        "",
        "Series preview:",
    ]
    for year, a, b, c in zip(years, p10, p50, p90):
        lines.append(f"Year {year}: P10=${a:,.2f} | P50=${b:,.2f} | P90=${c:,.2f}")
    Path(output_path).write_text("\n".join(lines), encoding="utf-8")
    return output_path


def try_build_chart(results_path: str = "power_efficiency_monte_carlo_results.json") -> str:
    results = load_results(results_path)

    try:
        import matplotlib.pyplot as plt  # type: ignore
    except ModuleNotFoundError:
        csv_path = write_csv(results)
        txt_path = write_text_summary(results)
        return f"matplotlib not available; wrote {csv_path} and {txt_path}"

    years, p10, p50, p90 = extract_series(results)

    fig = plt.figure(facecolor=BG, figsize=(12, 6), dpi=160)
    ax = fig.add_subplot(111)
    ax.set_facecolor(PANEL)

    ax.plot(years, [v / 1e6 for v in p10], color=P10_COLOR, linewidth=2.2, label="P10 Bearish")
    ax.plot(years, [v / 1e6 for v in p50], color=P50_COLOR, linewidth=2.8, label="P50 Base")
    ax.plot(years, [v / 1e6 for v in p90], color=P90_COLOR, linewidth=2.2, label="P90 Bullish")

    ax.fill_between(
        years,
        [v / 1e6 for v in p10],
        [v / 1e6 for v in p90],
        color=NEON,
        alpha=0.08,
        label="Probability Band",
    )

    ax.set_title("Power Efficiency Theory Monte Carlo Scenario Band", color=NEON, pad=14)
    ax.set_xlabel("Years From Start", color=NEON)
    ax.set_ylabel("Value (Millions USD)", color=NEON)

    ax.tick_params(colors=NEON)
    for spine in ax.spines.values():
        spine.set_color(NEON)

    ax.grid(True, color=NEON, alpha=0.12)

    legend = ax.legend(facecolor=PANEL, edgecolor=NEON)
    for text in legend.get_texts():
        text.set_color(MUTED)

    summary = results["summary"]
    note = (
        f"P10: ${summary['p10_final_value']:,.0f}   "
        f"P50: ${summary['p50_final_value']:,.0f}   "
        f"P90: ${summary['p90_final_value']:,.0f}"
    )
    ax.text(
        0.02,
        0.02,
        note,
        transform=ax.transAxes,
        color=MUTED,
        fontsize=9,
        bbox=dict(boxstyle="round,pad=0.25", fc=PANEL, ec=NEON, alpha=0.9),
    )

    plt.tight_layout()
    output_path = "power_efficiency_monte_carlo_chart.png"
    plt.savefig(output_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    return output_path


def main() -> None:
    output = try_build_chart()
    print(output)


if __name__ == "__main__":
    main()
