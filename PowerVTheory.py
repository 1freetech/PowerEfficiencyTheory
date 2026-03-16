import os
import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib

import numpy

import numpy as np
from PIL import Image, ImageTk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


class PowerEfficiencyCalculator:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Power Efficiency Theory Calculator | bitcoinversus.tech")
        self.root.geometry("1320x820")
        self.root.configure(bg="#000000")

        self.bg = "#000000"
        self.neon = "#39ff14"
        self.default_line = "orange"

        self._build_styles()
        self._build_layout()
        self._set_defaults()
        self._build_chart()
        self.update_chart()

    def _build_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "TLabel",
            background=self.bg,
            foreground=self.neon,
            font=("Arial", 11)
        )

        style.configure(
            "Title.TLabel",
            background=self.bg,
            foreground=self.neon,
            font=("Arial", 15, "bold")
        )

        style.configure(
            "TButton",
            background=self.bg,
            foreground=self.neon,
            borderwidth=1,
            focusthickness=3,
            focuscolor=self.neon
        )

        style.map(
            "TButton",
            background=[("active", "#101010")],
            foreground=[("active", self.neon)]
        )

        style.configure(
            "TEntry",
            fieldbackground="#050505",
            foreground=self.neon,
            insertcolor=self.neon
        )

    def _build_layout(self) -> None:
        self.root.grid_columnconfigure(0, weight=0)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        self.control_frame = tk.Frame(self.root, bg=self.bg, padx=14, pady=14)
        self.control_frame.grid(row=0, column=0, sticky="nsw")

        self.chart_frame = tk.Frame(self.root, bg=self.bg, padx=10, pady=10)
        self.chart_frame.grid(row=0, column=1, sticky="nsew")

        self._build_controls()

    def _build_controls(self) -> None:
        title_frame = tk.Frame(self.control_frame, bg=self.bg)
        title_frame.pack(anchor="w", fill="x", pady=(0, 10))

        logo_path = "bitcoinversus.tek.jpg"
        self.logo_label = tk.Label(title_frame, bg=self.bg)
        self.logo_label.pack(side="left", padx=(0, 8))

        if os.path.exists(logo_path):
            try:
                image = Image.open(logo_path)
                image.thumbnail((28, 28))
                self.logo_img = ImageTk.PhotoImage(image)
                self.logo_label.configure(image=self.logo_img)
            except Exception:
                self.logo_label.configure(text="B", fg=self.neon, bg=self.bg, font=("Arial", 12, "bold"))
        else:
            self.logo_label.configure(text="B", fg=self.neon, bg=self.bg, font=("Arial", 12, "bold"))

        ttk.Label(
            title_frame,
            text="bitcoinversus.tech",
            style="Title.TLabel"
        ).pack(side="left")

        ttk.Label(
            self.control_frame,
            text="Power Efficiency Theory Calculator",
            style="Title.TLabel"
        ).pack(anchor="w", pady=(6, 14))

        self.inputs: dict[str, tk.StringVar] = {}

        fields = [
            ("Start Value V0", "V0"),
            ("Power Growth p", "p"),
            ("Efficiency Improvement e", "e"),
            ("Initial Lag L0", "L0"),
            ("Lag Decay d", "d"),
            ("Start Year", "start_year"),
            ("End Year", "end_year"),
            ("Line Color", "line_color"),
            ("Chart Title", "chart_title"),
        ]

        for label_text, key in fields:
            row = tk.Frame(self.control_frame, bg=self.bg)
            row.pack(fill="x", pady=5)

            ttk.Label(row, text=label_text, width=22).pack(side="left")

            var = tk.StringVar()
            entry = tk.Entry(
                row,
                textvariable=var,
                bg="#050505",
                fg=self.neon,
                insertbackground=self.neon,
                relief="solid",
                bd=1,
                width=22,
                font=("Arial", 11)
            )
            entry.pack(side="left", padx=(6, 0))
            self.inputs[key] = var

        button_row = tk.Frame(self.control_frame, bg=self.bg)
        button_row.pack(fill="x", pady=(18, 10))

        tk.Button(
            button_row,
            text="Generate Chart",
            command=self.update_chart,
            bg="#050505",
            fg=self.neon,
            activebackground="#101010",
            activeforeground=self.neon,
            relief="solid",
            bd=1,
            font=("Arial", 11, "bold"),
            padx=10,
            pady=6
        ).pack(side="left")

        tk.Button(
            button_row,
            text="Reset Defaults",
            command=self._set_defaults,
            bg="#050505",
            fg=self.neon,
            activebackground="#101010",
            activeforeground=self.neon,
            relief="solid",
            bd=1,
            font=("Arial", 11),
            padx=10,
            pady=6
        ).pack(side="left", padx=(8, 0))

        info_text = (
        """
        Power Efficiency Theory states that the value of a thing at a future time t
        written as V(t), is determined by how fast its performance improves 
        and how quickly its energy cost per unit output declines.
        Over long time horizons, the compounding relationship 
        between computational power growth and efficiency improvements 
        provides a measurable technological foundation 
        for Bitcoin’s increasing economic value"""

        )

        info_box = tk.Label(
            self.control_frame,
            text=info_text,
            bg=self.bg,
            fg=self.neon,
            justify="left",
            font=("Consolas", 10),
            anchor="w"
        )
        info_box.pack(anchor="w", pady=(14, 0))

    def _set_defaults(self) -> None:
        defaults = {
            "V0": "75000",
            "p": "0.15",
            "e": "0.07",
            "L0": "0.50",
            "d": "0.15",
            "start_year": "2026",
            "end_year": "2046",
            "line_color": self.default_line,
            "chart_title": "Power Efficiency Compounding Scenarios",
        }

        for key, value in defaults.items():
            self.inputs[key].set(value)

    def _build_chart(self) -> None:
        self.figure = Figure(figsize=(10, 6), dpi=120, facecolor=self.bg)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor(self.bg)

        self.canvas = FigureCanvasTkAgg(self.figure, master=self.chart_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def update_chart(self) -> None:
        try:
            v0 = float(self.inputs["V0"].get())
            p = float(self.inputs["p"].get())
            e = float(self.inputs["e"].get())
            l0 = float(self.inputs["L0"].get())
            d = float(self.inputs["d"].get())
            start_year = int(self.inputs["start_year"].get())
            end_year = int(self.inputs["end_year"].get())
            line_color = self.inputs["line_color"].get().strip() or self.default_line
            chart_title = self.inputs["chart_title"].get().strip() or "Power Efficiency Compounding Scenarios"

            if end_year <= start_year:
                raise ValueError("End year must be greater than start year.")
            if e >= 1:
                raise ValueError("Efficiency improvement e must be less than 1.")
            if l0 >= 1.5:
                raise ValueError("Initial lag L0 is too large for this chart.")
        except ValueError as exc:
            messagebox.showerror("Invalid Input", str(exc))
            return

        years = np.arange(start_year, end_year + 1)
        x = years - start_year

        growth = (1 + p) / (1 - e)
        v_base = v0 * (growth ** x)
        lag_term = 1 - l0 * ((1 - d) ** x)
        v_decay = v_base * lag_term

        self.ax.clear()
        self.ax.set_facecolor(self.bg)

        # glow
        self.ax.plot(years, v_decay / 1e6, color=line_color, linewidth=8, alpha=0.10)
        self.ax.plot(years, v_decay / 1e6, color=line_color, linewidth=5, alpha=0.18)

        # main line
        self.ax.plot(
            years,
            v_decay / 1e6,
            color=line_color,
            linewidth=2.8,
            label="P Theory with decaying contraction"
        )

        # key labels
        milestone_years = [2030, 2035, 2040, 2045]
        for year in milestone_years:
            if year in years:
                idx = np.where(years == year)[0][0]
                val_m = v_decay[idx] / 1e6
                self.ax.scatter(year, val_m, color=line_color, s=28)
                self.ax.text(
                    year,
                    val_m + max(0.03, val_m * 0.04),
                    f"${v_decay[idx]:,.0f}",
                    color=self.neon,
                    fontsize=9,
                    ha="center"
                )

        self.ax.set_title(chart_title, color=self.neon, pad=14, fontsize=14)
        self.ax.set_xlabel("Year", color=self.neon, fontsize=11)
        self.ax.set_ylabel("Millions USD", color=self.neon, fontsize=11)

        self.ax.tick_params(colors=self.neon)
        for spine in self.ax.spines.values():
            spine.set_color(self.neon)

        self.ax.grid(True, color=self.neon, alpha=0.12)

        legend = self.ax.legend(facecolor=self.bg, edgecolor=self.neon, fontsize=9)
        for text in legend.get_texts():
            text.set_color(self.neon)

        self.figure.tight_layout()
        self.canvas.draw()


def main() -> None:
    root = tk.Tk()
    app = PowerEfficiencyCalculator(root)
    root.mainloop()


if __name__ == "__main__":
    main()
