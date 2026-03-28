import json
import os
import random
import tkinter as tk
from tkinter import filedialog, messagebox

import numpy as np
from PIL import Image, ImageTk
from matplotlib.animation import FuncAnimation
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


class ScrollableSidebar(tk.Frame):
    def __init__(self, parent: tk.Widget, bg: str, width: int = 430) -> None:
        super().__init__(parent, bg=bg, width=width)
        self.pack_propagate(False)

        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0, width=width)
        self.scrollbar = tk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)

        self.inner.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor='nw')
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(self.window_id, width=e.width))

        self.canvas.pack(side='left', fill='both', expand=True)
        self.scrollbar.pack(side='right', fill='y')

        self.canvas.bind_all('<MouseWheel>', self._on_mousewheel, add='+')
        self.canvas.bind_all('<Button-4>', self._on_mousewheel_linux, add='+')
        self.canvas.bind_all('<Button-5>', self._on_mousewheel_linux, add='+')

    def _pointer_inside_sidebar(self) -> bool:
        x_root, y_root = self.winfo_pointerxy()
        widget = self.winfo_containing(x_root, y_root)
        while widget is not None:
            if widget is self:
                return True
            widget = widget.master
        return False

    def _on_mousewheel(self, event: tk.Event) -> None:
        if self._pointer_inside_sidebar():
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

    def _on_mousewheel_linux(self, event: tk.Event) -> None:
        if not self._pointer_inside_sidebar():
            return
        if event.num == 4:
            self.canvas.yview_scroll(-1, 'units')
        elif event.num == 5:
            self.canvas.yview_scroll(1, 'units')


class PowerEfficiencySimulator:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title('Power Efficiency Theory Simulator 6.0 | BitcoinVersus.Tech')
        self.root.geometry('1520x980')
        self.root.minsize(1360, 900)
        self.root.configure(bg='#050505')

        self.bg = '#050505'
        self.panel = '#0b0b0b'
        self.panel_2 = '#101010'
        self.border = '#1c1c1c'
        self.neon = '#39ff14'
        self.muted = '#9cff8a'
        self.default_line_colors = ['#00ff37', '#f824ff', '#f10101', '#770ef8', '#1418ff']
        self.machine_curve_color = '#fd7e07'
        self.monte_carlo_color = '#00e5ff'
        self.machine_target_color = '#ffb347'
        self.model_target_color = self.neon
        self.scanline_color = '#8dff76'

        self.chart_animation = None
        self.radar_animation = None
        self.scanline_animation = None
        self.hover_animation = None

        self.model_scenarios: list[dict[str, tk.StringVar]] = []
        self.model_cards: list[tk.Frame] = []
        self.machine_scenarios: list[dict[str, tk.StringVar]] = []
        self.machine_cards: list[tk.Frame] = []
        self.metric_vars: dict[str, tk.StringVar] = {}
        self.current_series_list: list[dict] = []
        self.current_target_year: int | None = None
        self.machine_series_active = False

        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.logo_path = os.path.join(self.base_dir, 'bitcoinversus.tek.jpg')
        self.equation_path = os.path.join(self.base_dir, 'ptheoryequation.jpg')
        self.header_logo_img: ImageTk.PhotoImage | None = None
        self.equation_img: ImageTk.PhotoImage | None = None

        self.results_text = tk.StringVar(value='Run a simulation to generate a chart explanation here.')
        self.monte_enabled = tk.BooleanVar(value=False)
        self.monte_iterations = tk.StringVar(value='250')
        self.scenario_file = tk.StringVar(value='SCENARIO_LIBRARY.json')

        self.hover_outer = None
        self.hover_mid = None
        self.hover_core = None
        self.hover_label = None
        self.radar_outer = None
        self.radar_mid = None
        self.radar_core = None
        self.radar_label = None
        self.scanline = None

        self.radar_anchor_x: float | None = None
        self.radar_anchor_y: float | None = None
        self.radar_anchor_color: str | None = None
        self.radar_anchor_label: str = ''
        self.hover_active = False
        self.data_xmin: float | None = None
        self.data_xmax: float | None = None
        self.data_ymin: float | None = None
        self.data_ymax: float | None = None

        self._build_layout()
        self._build_chart()
        self._init_hover_artists()
        self._set_defaults()
        self.calculate_all_models(animated=False)

    def _resolve_asset(self, path: str) -> str | None:
        return path if os.path.exists(path) else None

    def _load_tk_image(self, path: str, size: tuple[int, int]) -> ImageTk.PhotoImage | None:
        asset = self._resolve_asset(path)
        if not asset:
            return None
        try:
            image = Image.open(asset)
            image = image.resize(size, Image.LANCZOS)
            return ImageTk.PhotoImage(image)
        except Exception:
            return None

    def _build_layout(self) -> None:
        self.root.grid_columnconfigure(0, weight=0)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        self.sidebar = ScrollableSidebar(self.root, bg=self.bg, width=440)
        self.sidebar.grid(row=0, column=0, sticky='nsw')
        self.control_frame = self.sidebar.inner

        self.chart_shell = tk.Frame(self.root, bg=self.bg, padx=12, pady=12)
        self.chart_shell.grid(row=0, column=1, sticky='nsew')
        self.chart_shell.grid_columnconfigure(0, weight=1)
        self.chart_shell.grid_rowconfigure(1, weight=1)

        self._build_controls()
        self._build_metrics()
        self._build_results_box()

    def _card(self, parent: tk.Widget, title: str) -> tk.Frame:
        card = tk.Frame(parent, bg=self.panel, padx=12, pady=12, highlightbackground=self.border, highlightthickness=1)
        card.pack(fill='x', pady=(0, 12))
        tk.Label(card, text=title, bg=self.panel, fg=self.neon, font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(0, 8))
        return card

    def _build_controls(self) -> None:
        header = tk.Frame(self.control_frame, bg=self.bg)
        header.pack(fill='x', pady=(16, 12), padx=16)

        logo_label = tk.Label(header, bg=self.bg)
        logo_label.pack(side='left', padx=(0, 10), anchor='nw')
        self.header_logo_img = self._load_tk_image(self.logo_path, (58, 58))
        if self.header_logo_img is not None:
            logo_label.configure(image=self.header_logo_img)
        else:
            logo_label.configure(text='B', fg=self.neon, bg=self.bg, font=('Segoe UI', 20, 'bold'))

        brand_wrap = tk.Frame(header, bg=self.bg)
        brand_wrap.pack(side='left', fill='x', anchor='nw')
        tk.Label(brand_wrap, text='BitcoinVersus.Tech', bg=self.bg, fg=self.neon, font=('Segoe UI', 18, 'bold')).pack(anchor='w')
        tk.Label(brand_wrap, text='Power Efficiency Theory Simulator 6.0', bg=self.bg, fg=self.muted, font=('Segoe UI', 10)).pack(anchor='w')

        outer = tk.Frame(self.control_frame, bg=self.bg, padx=16)
        outer.pack(fill='x')

        equation_box = tk.Frame(outer, bg=self.panel, padx=8, pady=8, highlightbackground=self.border, highlightthickness=1)
        equation_box.pack(fill='x', pady=(0, 12))
        self.equation_img = self._load_tk_image(self.equation_path, (390, 74))
        if self.equation_img is not None:
            tk.Label(equation_box, image=self.equation_img, bg=self.panel, bd=0, highlightthickness=0).pack(anchor='center')
        else:
            tk.Label(equation_box, text='Equation image not found', bg=self.panel, fg=self.muted, font=('Segoe UI', 11)).pack(anchor='center')

        model_module = tk.Frame(outer, bg=self.panel, padx=12, pady=12, highlightbackground=self.border, highlightthickness=1)
        model_module.pack(fill='x', pady=(0, 12))
        model_header = tk.Frame(model_module, bg=self.panel)
        model_header.pack(fill='x', pady=(0, 8))
        tk.Label(model_header, text='POWER EFFICIENCY SIMULATOR', bg=self.panel, fg=self.neon, font=('Segoe UI', 11, 'bold')).pack(side='left')
        tk.Button(model_header, text='+', command=self.add_model_widget, bg=self.panel_2, fg=self.neon, activebackground=self.panel, activeforeground=self.neon, relief='flat', bd=0, font=('Segoe UI', 12, 'bold'), width=3, cursor='hand2', highlightbackground=self.border, highlightthickness=1).pack(side='right')
        self.models_container = tk.Frame(model_module, bg=self.panel)
        self.models_container.pack(fill='x')
        self.add_model_widget(initial=True)

        model_buttons = tk.Frame(outer, bg=self.bg)
        model_buttons.pack(fill='x', pady=(0, 12))
        tk.Button(model_buttons, text='Calculate Model(s)', command=self.calculate_all_models, bg=self.neon, fg='#000000', activebackground='#7dff63', activeforeground='#000000', relief='flat', bd=0, font=('Segoe UI', 10, 'bold'), padx=16, pady=8, cursor='hand2').pack(side='left')
        tk.Button(model_buttons, text='Reset Model(s)', command=self._reset_models_and_refresh, bg=self.panel, fg=self.neon, activebackground=self.panel_2, activeforeground=self.neon, relief='flat', bd=0, font=('Segoe UI', 10), padx=16, pady=8, cursor='hand2', highlightbackground=self.border, highlightthickness=1).pack(side='left', padx=(8, 0))

        machine_module = tk.Frame(outer, bg=self.panel, padx=12, pady=12, highlightbackground=self.border, highlightthickness=1)
        machine_module.pack(fill='x', pady=(0, 12))
        machine_header = tk.Frame(machine_module, bg=self.panel)
        machine_header.pack(fill='x', pady=(0, 8))
        tk.Label(machine_header, text='ASIC MACHINE MINING METRICS SIMULATOR', bg=self.panel, fg=self.neon, font=('Segoe UI', 10, 'bold')).pack(side='left')
        tk.Button(machine_header, text='+', command=self.add_machine_widget, bg=self.panel_2, fg=self.neon, activebackground=self.panel, activeforeground=self.neon, relief='flat', bd=0, font=('Segoe UI', 12, 'bold'), width=3, cursor='hand2', highlightbackground=self.border, highlightthickness=1).pack(side='right')
        self.machine_container = tk.Frame(machine_module, bg=self.panel)
        self.machine_container.pack(fill='x')
        self.add_machine_widget(initial=True)

        monte_card = self._card(outer, 'MONTE CARLO OVERLAY')
        tk.Checkbutton(monte_card, text='Enable Monte Carlo percentile overlay', variable=self.monte_enabled, bg=self.panel, fg=self.neon, selectcolor=self.panel_2, activebackground=self.panel, activeforeground=self.neon).pack(anchor='w')
        monte_row = tk.Frame(monte_card, bg=self.panel)
        monte_row.pack(fill='x', pady=(8, 0))
        tk.Label(monte_row, text='Iterations', bg=self.panel, fg=self.neon, width=18, anchor='w').pack(side='left')
        tk.Entry(monte_row, textvariable=self.monte_iterations, bg=self.panel_2, fg=self.neon, insertbackground=self.neon, relief='flat', bd=0, highlightthickness=1, highlightbackground=self.border, highlightcolor=self.neon, width=18, font=('Consolas', 10)).pack(side='left', padx=(8, 0), ipady=5)

        scenario_row = tk.Frame(monte_card, bg=self.panel)
        scenario_row.pack(fill='x', pady=(8, 0))
        tk.Label(scenario_row, text='Scenario File', bg=self.panel, fg=self.neon, width=18, anchor='w').pack(side='left')
        tk.Entry(scenario_row, textvariable=self.scenario_file, bg=self.panel_2, fg=self.neon, insertbackground=self.neon, relief='flat', bd=0, highlightthickness=1, highlightbackground=self.border, highlightcolor=self.neon, width=24, font=('Consolas', 10)).pack(side='left', padx=(8, 0), ipady=5)

        info_card = self._card(outer, 'WHAT IS NEW IN 6.0')
        info_text = (
            'Version 6.0 adds a practical bridge between the original deterministic simulator and the new monetization-oriented modeling work. '
            'It keeps the multi-scenario and machine modules, while adding an optional Monte Carlo percentile overlay and scenario-file support.'
        )
        tk.Label(info_card, text=info_text, bg=self.panel, fg=self.muted, justify='left', wraplength=370, font=('Segoe UI', 10)).pack(anchor='w')

    def add_model_widget(self, initial: bool = False) -> None:
        if len(self.model_scenarios) >= 5:
            if not initial:
                messagebox.showinfo('Limit Reached', 'You can compare up to 5 model widgets at once.')
            return
        index = len(self.model_scenarios) + 1
        card = tk.Frame(self.models_container, bg=self.panel, padx=12, pady=12, highlightbackground=self.border, highlightthickness=0)
        card.pack(fill='x', pady=(0, 12))
        title_row = tk.Frame(card, bg=self.panel)
        title_row.pack(fill='x', pady=(0, 8))
        tk.Label(title_row, text=f'Scenario {index}', bg=self.panel, fg=self.neon, font=('Segoe UI', 10, 'bold')).pack(side='left')
        if index > 1:
            tk.Button(title_row, text='−', command=lambda c=card: self.remove_model_widget(c), bg=self.panel_2, fg=self.neon, activebackground=self.panel, activeforeground=self.neon, relief='flat', bd=0, font=('Segoe UI', 11, 'bold'), width=3, cursor='hand2', highlightbackground=self.border, highlightthickness=1).pack(side='right')

        fields: dict[str, tk.StringVar] = {}
        for label_text, key in [('Start Value V0', 'V0'), ('Power Growth p', 'p'), ('Efficiency Improvement e', 'e'), ('Initial Lag L', 'L0'), ('Lag Decay d', 'd'), ('Start Year', 'start_year'), ('End Year', 'end_year')]:
            row = tk.Frame(card, bg=self.panel)
            row.pack(fill='x', pady=4)
            tk.Label(row, text=label_text, bg=self.panel, fg=self.neon, font=('Segoe UI', 10), width=18, anchor='w').pack(side='left')
            var = tk.StringVar()
            tk.Entry(row, textvariable=var, bg=self.panel_2, fg=self.neon, insertbackground=self.neon, relief='flat', bd=0, highlightthickness=1, highlightbackground=self.border, highlightcolor=self.neon, width=18, font=('Consolas', 10)).pack(side='left', padx=(8, 0), ipady=5)
            fields[key] = var
        self.model_cards.append(card)
        self.model_scenarios.append(fields)
        self._apply_model_defaults(fields, index - 1)

    def remove_model_widget(self, card: tk.Frame) -> None:
        if len(self.model_cards) <= 1:
            return
        idx = self.model_cards.index(card)
        self.model_cards.pop(idx)
        self.model_scenarios.pop(idx)
        card.destroy()
        self._refresh_titles(self.model_cards, 'Scenario')
        self.calculate_all_models(animated=False)

    def add_machine_widget(self, initial: bool = False) -> None:
        if len(self.machine_scenarios) >= 5:
            if not initial:
                messagebox.showinfo('Limit Reached', 'You can compare up to 5 machine widgets at once.')
            return
        index = len(self.machine_scenarios) + 1
        card = tk.Frame(self.machine_container, bg=self.panel, padx=12, pady=12, highlightbackground=self.border, highlightthickness=0)
        card.pack(fill='x', pady=(0, 12))
        title_row = tk.Frame(card, bg=self.panel)
        title_row.pack(fill='x', pady=(0, 8))
        tk.Label(title_row, text=f'Machine {index}', bg=self.panel, fg=self.neon, font=('Segoe UI', 10, 'bold')).pack(side='left')
        if index > 1:
            tk.Button(title_row, text='−', command=lambda c=card: self.remove_machine_widget(c), bg=self.panel_2, fg=self.neon, activebackground=self.panel, activeforeground=self.neon, relief='flat', bd=0, font=('Segoe UI', 11, 'bold'), width=3, cursor='hand2', highlightbackground=self.border, highlightthickness=1).pack(side='right')

        fields: dict[str, tk.StringVar] = {}
        for label_text, key in [('Start Year', 'metric_start_year'), ('Start J/TH', 'start_jth'), ('End Year', 'metric_end_year'), ('End J/TH', 'end_jth'), ('End Machine Watts', 'watts'), ('End Hashrate TH/s', 'hashrate_th')]:
            row = tk.Frame(card, bg=self.panel)
            row.pack(fill='x', pady=4)
            tk.Label(row, text=label_text, bg=self.panel, fg=self.neon, font=('Segoe UI', 10), width=18, anchor='w').pack(side='left')
            var = tk.StringVar()
            tk.Entry(row, textvariable=var, bg=self.panel_2, fg=self.neon, insertbackground=self.neon, relief='flat', bd=0, highlightthickness=1, highlightbackground=self.border, highlightcolor=self.neon, width=18, font=('Consolas', 10)).pack(side='left', padx=(8, 0), ipady=5)
            fields[key] = var
        self.machine_cards.append(card)
        self.machine_scenarios.append(fields)
        self._apply_machine_defaults(fields, index - 1)

    def remove_machine_widget(self, card: tk.Frame) -> None:
        if len(self.machine_cards) <= 1:
            return
        idx = self.machine_cards.index(card)
        self.machine_cards.pop(idx)
        self.machine_scenarios.pop(idx)
        card.destroy()
        self._refresh_titles(self.machine_cards, 'Machine')
        self.calculate_all_models(animated=False)

    def _refresh_titles(self, cards: list[tk.Frame], prefix: str) -> None:
        for idx, card in enumerate(cards, start=1):
            title_row = card.winfo_children()[0]
            title_label = title_row.winfo_children()[0]
            if isinstance(title_label, tk.Label):
                title_label.config(text=f'{prefix} {idx}')

    def _build_metrics(self) -> None:
        metrics_frame = tk.Frame(self.chart_shell, bg=self.bg)
        metrics_frame.grid(row=0, column=0, sticky='ew', pady=(0, 10))
        for i in range(10):
            metrics_frame.grid_columnconfigure(i, weight=1)
        metric_defs = [
            ('Final Value', 'final_value'), ('Growth Multiple', 'growth_multiple'), ('Growth Ratio', 'growth_ratio'),
            ('Derived J/TH', 'derived_jth'), ('Efficiency Rate', 'eff_delta'), ('Target Year Value', 'target_value'),
            ('Years Modeled', 'years_modeled'), ('Implied End J/TH', 'implied_end_jth'), ('Implied End TH/s', 'implied_end_hashrate'),
            ('Monte Carlo P50', 'monte_p50'),
        ]
        for col, (label, key) in enumerate(metric_defs):
            card = tk.Frame(metrics_frame, bg=self.panel, padx=10, pady=8, highlightbackground=self.border, highlightthickness=1)
            card.grid(row=0, column=col, sticky='nsew', padx=(0 if col == 0 else 6, 0))
            self.metric_vars[key] = tk.StringVar(value='--')
            tk.Label(card, text=label, bg=self.panel, fg=self.muted, font=('Segoe UI', 8)).pack(anchor='w')
            tk.Label(card, textvariable=self.metric_vars[key], bg=self.panel, fg=self.neon, font=('Consolas', 10, 'bold')).pack(anchor='w', pady=(4, 0))

    def _build_results_box(self) -> None:
        controls_row = tk.Frame(self.chart_shell, bg=self.bg)
        controls_row.grid(row=2, column=0, sticky='ew', pady=(10, 8))
        tk.Button(controls_row, text='Download Chart', command=self._download_chart, bg=self.panel, fg=self.neon, activebackground=self.panel_2, activeforeground=self.neon, relief='flat', bd=0, font=('Segoe UI', 10, 'bold'), padx=16, pady=8, cursor='hand2', highlightbackground=self.border, highlightthickness=1).grid(row=0, column=0, sticky='w')
        tk.Button(controls_row, text='Load Scenario JSON', command=self._load_scenario_file, bg=self.panel, fg=self.neon, activebackground=self.panel_2, activeforeground=self.neon, relief='flat', bd=0, font=('Segoe UI', 10, 'bold'), padx=16, pady=8, cursor='hand2', highlightbackground=self.border, highlightthickness=1).grid(row=0, column=1, sticky='w', padx=(8, 0))
        results_card = tk.Frame(self.chart_shell, bg=self.panel, padx=12, pady=12, highlightbackground=self.border, highlightthickness=1)
        results_card.grid(row=3, column=0, sticky='ew')
        tk.Label(results_card, text='RESULTS EXPLANATION', bg=self.panel, fg=self.neon, font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(0, 6))
        tk.Label(results_card, textvariable=self.results_text, bg=self.panel, fg=self.muted, justify='left', wraplength=900, font=('Segoe UI', 9)).pack(anchor='w')

    def _build_chart(self) -> None:
        chart_frame = tk.Frame(self.chart_shell, bg=self.panel, padx=8, pady=8, highlightbackground=self.border, highlightthickness=1)
        chart_frame.grid(row=1, column=0, sticky='nsew')
        chart_frame.grid_rowconfigure(0, weight=1)
        chart_frame.grid_columnconfigure(0, weight=1)
        self.figure = Figure(figsize=(8.4, 5.1), dpi=125, facecolor=self.panel)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor(self.panel)
        self.canvas = FigureCanvasTkAgg(self.figure, master=chart_frame)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky='nsew')
        self.canvas.mpl_connect('motion_notify_event', self._on_chart_hover)
        self.canvas.mpl_connect('figure_leave_event', self._on_chart_leave)
        self.canvas.mpl_connect('scroll_event', self._on_chart_scroll)

    def _init_hover_artists(self) -> None:
        self.hover_outer = self.ax.scatter([], [], s=520, facecolors='none', edgecolors=self.neon, linewidths=1.0, alpha=0.08, zorder=20, visible=False)
        self.hover_mid = self.ax.scatter([], [], s=220, facecolors='none', edgecolors=self.neon, linewidths=1.2, alpha=0.24, zorder=21, visible=False)
        self.hover_core = self.ax.scatter([], [], s=34, color=self.neon, alpha=0.96, zorder=22, visible=False)
        self.hover_label = self.ax.annotate('', xy=(0, 0), xytext=(12, 12), textcoords='offset points', color=self.neon, fontsize=8, fontname='Consolas', bbox=dict(boxstyle='round,pad=0.22', fc=self.panel_2, ec=self.border, alpha=0.94), visible=False, zorder=23)

    def _create_radar_artists(self) -> None:
        self.radar_outer = self.ax.scatter([], [], s=320, facecolors='none', edgecolors=self.neon, linewidths=1.2, alpha=0.18, zorder=13, visible=False)
        self.radar_mid = self.ax.scatter([], [], s=140, facecolors='none', edgecolors=self.neon, linewidths=1.3, alpha=0.34, zorder=14, visible=False)
        self.radar_core = self.ax.scatter([], [], s=26, color=self.neon, alpha=0.95, zorder=15, visible=False)
        self.radar_label = self.ax.annotate('', xy=(0, 0), xytext=(12, 14), textcoords='offset points', color=self.neon, fontsize=8, fontname='Consolas', bbox=dict(boxstyle='round,pad=0.22', fc=self.panel_2, ec=self.border, alpha=0.94), visible=False, zorder=16)

    def _set_defaults(self) -> None:
        self._reset_models()
        self._reset_machine_inputs()

    def _apply_model_defaults(self, fields: dict[str, tk.StringVar], idx: int) -> None:
        presets = [
            {'V0': '75000', 'p': '0.15', 'e': '0.07', 'L0': '0.50', 'd': '0.15', 'start_year': '2025', 'end_year': '2040'},
            {'V0': '75000', 'p': '0.18', 'e': '0.10', 'L0': '0.45', 'd': '0.16', 'start_year': '2025', 'end_year': '2040'},
            {'V0': '75000', 'p': '0.21', 'e': '0.15', 'L0': '0.42', 'd': '0.18', 'start_year': '2025', 'end_year': '2040'},
            {'V0': '75000', 'p': '0.25', 'e': '0.18', 'L0': '0.38', 'd': '0.20', 'start_year': '2025', 'end_year': '2040'},
            {'V0': '75000', 'p': '0.30', 'e': '0.21', 'L0': '0.35', 'd': '0.22', 'start_year': '2025', 'end_year': '2040'},
        ]
        preset = presets[min(idx, len(presets) - 1)]
        for key, value in preset.items():
            fields[key].set(value)

    def _apply_machine_defaults(self, fields: dict[str, tk.StringVar], idx: int) -> None:
        presets = [
            {'metric_start_year': '2025', 'start_jth': '9.5', 'metric_end_year': '2034', 'end_jth': '4.75', 'watts': '', 'hashrate_th': ''},
            {'metric_start_year': '2025', 'start_jth': '9.5', 'metric_end_year': '2036', 'end_jth': '3.90', 'watts': '', 'hashrate_th': ''},
            {'metric_start_year': '2025', 'start_jth': '9.5', 'metric_end_year': '2038', 'end_jth': '3.20', 'watts': '', 'hashrate_th': ''},
            {'metric_start_year': '2025', 'start_jth': '9.5', 'metric_end_year': '2040', 'end_jth': '2.70', 'watts': '', 'hashrate_th': ''},
            {'metric_start_year': '2025', 'start_jth': '9.5', 'metric_end_year': '2042', 'end_jth': '2.20', 'watts': '', 'hashrate_th': ''},
        ]
        preset = presets[min(idx, len(presets) - 1)]
        for key, value in preset.items():
            fields[key].set(value)

    def _reset_models(self) -> None:
        while len(self.model_cards) > 1:
            self.model_cards.pop().destroy()
            self.model_scenarios.pop()
        if not self.model_scenarios:
            self.add_model_widget(initial=True)
        self._apply_model_defaults(self.model_scenarios[0], 0)
        self._refresh_titles(self.model_cards, 'Scenario')

    def _reset_machine_inputs(self) -> None:
        while len(self.machine_cards) > 1:
            self.machine_cards.pop().destroy()
            self.machine_scenarios.pop()
        if not self.machine_scenarios:
            self.add_machine_widget(initial=True)
        self._apply_machine_defaults(self.machine_scenarios[0], 0)
        self._refresh_titles(self.machine_cards, 'Machine')

    def _reset_machine_and_refresh(self) -> None:
        self._reset_machine_inputs()
        self.calculate_all_models(animated=False)

    def _reset_models_and_refresh(self) -> None:
        self._reset_models()
        self.calculate_all_models(animated=False)

    def _stop_animations(self) -> None:
        for anim in (self.chart_animation, self.radar_animation, self.scanline_animation, self.hover_animation):
            if anim is not None and getattr(anim, 'event_source', None) is not None:
                anim.event_source.stop()
        self.chart_animation = self.radar_animation = self.scanline_animation = self.hover_animation = None

    def _build_price_series(self, v0: float, p: float, e: float, l0: float, d: float, start_year: int, end_year: int) -> dict:
        if end_year <= start_year:
            raise ValueError('End year must be greater than start year.')
        if e >= 1:
            raise ValueError('Efficiency improvement e must be less than 1.')
        if 1 + p <= 0:
            raise ValueError('Power growth p must keep (1 + p) above 0.')
        if l0 >= 1.5:
            raise ValueError('Initial lag L is too large for this chart.')
        years = np.arange(start_year, end_year + 1)
        x = years - start_year
        growth = (1 + p) / (1 - e)
        v_base = v0 * (growth ** x)
        lag_term = 1 - l0 * ((1 - d) ** x)
        values = v_base * lag_term
        return {'years': years, 'raw_values': values, 'values_m': values / 1e6, 'growth': growth}

    def _collect_model_series(self) -> list[dict]:
        parsed = []
        for idx, fields in enumerate(self.model_scenarios, start=1):
            series = self._build_price_series(float(fields['V0'].get()), float(fields['p'].get()), float(fields['e'].get()), float(fields['L0'].get()), float(fields['d'].get()), int(fields['start_year'].get()), int(fields['end_year'].get()))
            series['label'] = f'P Theory Scenario {idx}'
            series['color'] = self.default_line_colors[(idx - 1) % len(self.default_line_colors)]
            parsed.append(series)
        return parsed

    def _collect_machine_series(self) -> tuple[list[dict], dict | None]:
        machine_series_list: list[dict] = []
        first_machine_summary: dict | None = None
        if not self.machine_scenarios:
            return machine_series_list, first_machine_summary
        base_fields = self.model_scenarios[0]
        v0 = float(base_fields['V0'].get())
        p = float(base_fields['p'].get())
        l0 = float(base_fields['L0'].get())
        d = float(base_fields['d'].get())
        for idx, fields in enumerate(self.machine_scenarios, start=1):
            metric_start_year = int(fields['metric_start_year'].get())
            metric_end_year = int(fields['metric_end_year'].get())
            start_jth = float(fields['start_jth'].get())
            watts_text = fields['watts'].get().strip()
            hashrate_text = fields['hashrate_th'].get().strip()
            end_jth_text = fields['end_jth'].get().strip()
            if metric_end_year <= metric_start_year:
                raise ValueError(f'Machine {idx}: end year must be greater than start year.')
            if start_jth <= 0:
                raise ValueError(f'Machine {idx}: start J/TH must be greater than 0.')
            if watts_text and hashrate_text:
                watts = float(watts_text)
                hashrate_th = float(hashrate_text)
                if watts <= 0 or hashrate_th <= 0:
                    raise ValueError(f'Machine {idx}: watts and hashrate must be greater than 0.')
                end_jth = watts / hashrate_th
            else:
                if not end_jth_text:
                    raise ValueError(f'Machine {idx}: provide either End J/TH or both End Machine Watts and End Hashrate TH/s.')
                end_jth = float(end_jth_text)
                watts = float(watts_text) if watts_text else 3500.0
                hashrate_th = watts / end_jth
            annual_eff_improvement = 1 - (end_jth / start_jth) ** (1 / (metric_end_year - metric_start_year))
            series = self._build_price_series(v0, p, annual_eff_improvement, l0, d, metric_start_year, metric_end_year)
            series['label'] = f'Machine {idx} Derived Curve ({annual_eff_improvement:.2%}/yr)'
            series['color'] = self.machine_curve_color if idx == 1 else self.default_line_colors[(idx - 1) % len(self.default_line_colors)]
            machine_series_list.append(series)
            if idx == 1:
                first_machine_summary = {'metric_start_year': metric_start_year, 'metric_end_year': metric_end_year, 'start_jth': start_jth, 'end_jth': end_jth, 'watts': watts, 'hashrate_th': hashrate_th, 'annual_eff_improvement': annual_eff_improvement, 'series': series}
        return machine_series_list, first_machine_summary

    def _build_monte_carlo_overlay(self, base_series: dict, iterations: int) -> dict:
        years = base_series['years']
        base_values = base_series['raw_values']
        samples = []
        for _ in range(iterations):
            curve = []
            for value in base_values:
                noise = random.gauss(1.0, 0.08)
                curve.append(max(0.0, value * noise))
            samples.append(curve)
        arr = np.array(samples)
        p10 = np.percentile(arr, 10, axis=0)
        p50 = np.percentile(arr, 50, axis=0)
        p90 = np.percentile(arr, 90, axis=0)
        return {'years': years, 'p10': p10, 'p50': p50, 'p90': p90}

    def calculate_all_models(self, animated: bool = True) -> None:
        try:
            parsed = self._collect_model_series()
        except ValueError as exc:
            messagebox.showerror('Invalid Input', str(exc))
            return
        self.machine_series_active = False
        self.current_series_list = parsed
        self.current_target_year = None
        first = parsed[0]
        base_fields = self.model_scenarios[0]
        start_year = int(base_fields['start_year'].get())
        end_year = int(base_fields['end_year'].get())
        years_elapsed = end_year - start_year
        e = float(base_fields['e'].get())
        baseline_jth = 9.5
        baseline_watts = 3500.0
        implied_end_jth = baseline_jth * ((1 - e) ** years_elapsed)
        implied_end_hashrate = baseline_watts / implied_end_jth
        self.metric_vars['final_value'].set(f"${first['raw_values'][-1]:,.0f}")
        self.metric_vars['growth_multiple'].set(f"{(first['raw_values'][-1] / first['raw_values'][0]):,.2f}x")
        self.metric_vars['growth_ratio'].set(f"{first['growth']:.4f}")
        self.metric_vars['derived_jth'].set('--')
        self.metric_vars['eff_delta'].set(f'{e:.2%}/yr')
        self.metric_vars['target_value'].set('--')
        self.metric_vars['years_modeled'].set(str(len(first['years']) - 1))
        self.metric_vars['implied_end_jth'].set(f'{implied_end_jth:,.2f} J/TH')
        self.metric_vars['implied_end_hashrate'].set(f'{implied_end_hashrate:,.0f} TH/s')
        self.metric_vars['monte_p50'].set('--')

        monte_summary = ''
        if self.monte_enabled.get():
            try:
                overlay = self._build_monte_carlo_overlay(first, int(self.monte_iterations.get()))
                self.metric_vars['monte_p50'].set(f"${overlay['p50'][-1]:,.0f}")
                first['monte_overlay'] = overlay
                monte_summary = f" Monte Carlo median end value is ${overlay['p50'][-1]:,.0f}, with P10 ${overlay['p10'][-1]:,.0f} and P90 ${overlay['p90'][-1]:,.0f}."
            except ValueError:
                pass

        self.results_text.set(
            f"Scenario 1 projects a final value of ${first['raw_values'][-1]:,.0f} across {len(first['years']) - 1} modeled years, "
            f"with compounded growth ratio {first['growth']:.4f}. The implied machine path moves from 9.50 J/TH to {implied_end_jth:,.2f} J/TH by {end_year}, "
            f"corresponding to {implied_end_hashrate:,.0f} TH/s at {baseline_watts:,.0f} watts.{monte_summary}"
        )
        self._render_chart(parsed, animated=animated, target_year=None)

    def calculate_from_mining_inputs(self) -> None:
        try:
            scenario_series = self._collect_model_series()
            machine_series_list, first_machine_summary = self._collect_machine_series()
        except ValueError as exc:
            messagebox.showerror('Invalid Input', str(exc))
            return
        if not first_machine_summary:
            messagebox.showerror('Invalid Input', 'At least one machine module is required.')
            return
        all_series = scenario_series + machine_series_list
        self.machine_series_active = True
        self.current_series_list = all_series
        self.current_target_year = first_machine_summary['metric_end_year']
        first_series = first_machine_summary['series']
        self.metric_vars['derived_jth'].set(f"{first_machine_summary['end_jth']:,.2f} J/TH")
        self.metric_vars['eff_delta'].set(f"{first_machine_summary['annual_eff_improvement']:.2%}/yr")
        self.metric_vars['target_value'].set(f"${first_series['raw_values'][-1]:,.0f}")
        self.metric_vars['final_value'].set(f"${first_series['raw_values'][-1]:,.0f}")
        self.metric_vars['growth_multiple'].set(f"{(first_series['raw_values'][-1] / first_series['raw_values'][0]):,.2f}x")
        self.metric_vars['growth_ratio'].set(f"{first_series['growth']:.4f}")
        self.metric_vars['years_modeled'].set(str(first_machine_summary['metric_end_year'] - first_machine_summary['metric_start_year']))
        self.metric_vars['implied_end_jth'].set('--')
        self.metric_vars['implied_end_hashrate'].set('--')
        self.results_text.set(
            f"Machine 1 inferred an annual efficiency improvement rate of {first_machine_summary['annual_eff_improvement']:.2%} from "
            f"{first_machine_summary['start_jth']:.2f} J/TH in {first_machine_summary['metric_start_year']} to {first_machine_summary['end_jth']:.2f} J/TH in {first_machine_summary['metric_end_year']}. "
            f"Using Scenario 1 as the structural base, the derived curve projects final value ${first_series['raw_values'][-1]:,.0f}."
        )
        self._render_chart(all_series, animated=True, target_year=first_machine_summary['metric_end_year'])

    def _render_chart(self, series_list: list[dict], animated: bool = True, target_year: int | None = None) -> None:
        self._stop_animations()
        self.ax.clear()
        self.ax.set_facecolor(self.panel)
        self.ax.set_title('Power Efficiency Compounding Scenarios', color=self.neon, fontsize=15, pad=16, fontname='Segoe UI', fontweight='bold')
        self.ax.set_xlabel('Year', color=self.neon, fontsize=10, fontname='Segoe UI')
        self.ax.set_ylabel('Millions USD', color=self.neon, fontsize=10, fontname='Segoe UI')
        self.ax.tick_params(colors=self.neon, labelsize=9)
        self.ax.grid(True, color=self.neon, alpha=0.08, linewidth=0.7)
        for spine in self.ax.spines.values():
            spine.set_color(self.border)
            spine.set_linewidth(1.1)

        all_years = np.concatenate([series['years'] for series in series_list])
        all_values = np.concatenate([series['values_m'] for series in series_list])
        xmin = float(np.min(all_years)); xmax = float(np.max(all_years)); ymin = float(np.min(all_values)); ymax = float(np.max(all_values))
        xpad = max(1.0, (xmax - xmin) * 0.06)
        ypad = max(0.05, (ymax - ymin) * 0.12 if ymax > ymin else ymax * 0.12 + 0.05)
        self.data_xmin, self.data_xmax, self.data_ymin, self.data_ymax = xmin - xpad, xmax + xpad, max(0.0, ymin - ypad), ymax + ypad
        self.ax.set_xlim(self.data_xmin, self.data_xmax)
        self.ax.set_ylim(self.data_ymin, self.data_ymax)

        for series in series_list:
            self.ax.plot(series['years'], series['values_m'], color=series['color'], linewidth=5, alpha=0.10)
            self.ax.plot(series['years'], series['values_m'], color=series['color'], linewidth=2.8, label=series['label'])
            if 'monte_overlay' in series:
                overlay = series['monte_overlay']
                self.ax.plot(overlay['years'], overlay['p50'] / 1e6, color=self.monte_carlo_color, linewidth=2.4, linestyle='--', label='Monte Carlo P50')
                self.ax.fill_between(overlay['years'], overlay['p10'] / 1e6, overlay['p90'] / 1e6, color=self.monte_carlo_color, alpha=0.08, label='Monte Carlo Band')

        legend = self.ax.legend(facecolor=self.panel_2, edgecolor=self.border, fontsize=8, loc='upper left')
        for text in legend.get_texts():
            text.set_color(self.neon)
        self.canvas.draw_idle()

    def _download_chart(self) -> None:
        filepath = filedialog.asksaveasfilename(title='Save Chart As', defaultextension='.png', filetypes=[('PNG files', '*.png')], initialfile='power_efficiency_chart_6_0.png')
        if not filepath:
            return
        try:
            self.figure.savefig(filepath, dpi=180, facecolor=self.figure.get_facecolor(), bbox_inches='tight')
            messagebox.showinfo('Chart Saved', f'Chart saved to:\n{filepath}')
        except Exception as exc:
            messagebox.showerror('Save Failed', str(exc))

    def _load_scenario_file(self) -> None:
        filepath = filedialog.askopenfilename(title='Load Scenario JSON', filetypes=[('JSON files', '*.json')])
        if not filepath:
            return
        self.scenario_file.set(filepath)
        try:
            data = json.loads(open(filepath, 'r', encoding='utf-8').read())
            scenarios = data.get('scenarios', [])
            if scenarios and self.model_scenarios:
                scenario = scenarios[0]
                mapping = {'start_value': 'V0', 'power_growth_mean': 'p', 'efficiency_improvement_mean': 'e', 'lag_start': 'L0', 'lag_decay': 'd', 'years': 'end_year'}
                base = self.model_scenarios[0]
                start_year = int(base['start_year'].get())
                for source_key, target_key in mapping.items():
                    if source_key in scenario and target_key in base:
                        if target_key == 'end_year':
                            base[target_key].set(str(start_year + int(scenario[source_key])))
                        else:
                            base[target_key].set(str(scenario[source_key]))
                self.calculate_all_models(animated=False)
        except Exception as exc:
            messagebox.showerror('Scenario Load Failed', str(exc))

    def _on_chart_leave(self, _event) -> None:
        pass

    def _on_chart_hover(self, _event) -> None:
        pass

    def _on_chart_scroll(self, event) -> None:
        if event.inaxes != self.ax or event.xdata is None or event.ydata is None:
            return
        cur_xlim = self.ax.get_xlim(); cur_ylim = self.ax.get_ylim()
        base_scale = 1.18
        scale_factor = 1 / base_scale if event.button == 'up' else base_scale
        new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
        new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor
        relx = (cur_xlim[1] - event.xdata) / (cur_xlim[1] - cur_xlim[0])
        rely = (cur_ylim[1] - event.ydata) / (cur_ylim[1] - cur_ylim[0])
        x_min = event.xdata - new_width * (1 - relx)
        x_max = event.xdata + new_width * relx
        y_min = event.ydata - new_height * (1 - rely)
        y_max = event.ydata + new_height * rely
        self.ax.set_xlim(x_min, x_max)
        self.ax.set_ylim(max(0.0, y_min), y_max)
        self.canvas.draw_idle()


def main() -> None:
    root = tk.Tk()
    PowerEfficiencySimulator(root)
    root.mainloop()


if __name__ == '__main__':
    main()
