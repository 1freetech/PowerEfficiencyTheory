import os
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

        self.inner.bind(
            '<Configure>',
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')),
        )

        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor='nw')
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind(
            '<Configure>',
            lambda e: self.canvas.itemconfigure(self.window_id, width=e.width),
        )

        self.canvas.pack(side='left', fill='both', expand=True)
        self.scrollbar.pack(side='right', fill='y')

        self.canvas.bind_all('<MouseWheel>', self._on_mousewheel)

    def _on_mousewheel(self, event: tk.Event) -> None:
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')


class PowerEfficiencySimulator:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title('Power Efficiency Theory Simulator | BitcoinVersus.Tech')
        self.root.geometry('1480x960')
        self.root.minsize(1340, 860)
        self.root.configure(bg='#050505')

        self.bg = '#050505'
        self.panel = '#0b0b0b'
        self.panel_2 = '#101010'
        self.border = '#1c1c1c'
        self.neon = '#39ff14'
        self.muted = '#9cff8a'
        self.default_line_colors = ['#00ff37', '#f824ff', '#f10101', '#770ef8', '#1418ff']
        self.machine_curve_color = '#fd7e07'

        self.chart_animation = None

        self.model_scenarios: list[dict[str, tk.StringVar]] = []
        self.model_cards: list[tk.Frame] = []

        self.machine_scenarios: list[dict[str, tk.StringVar]] = []
        self.machine_cards: list[tk.Frame] = []

        self.metric_vars: dict[str, tk.StringVar] = {}
        self.last_years: np.ndarray | None = None
        self.last_raw_values: list[np.ndarray] = []
        self.machine_series_active = False

        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.logo_path = os.path.join(self.base_dir, 'bitcoinversus.tek.jpg')
        self.equation_path = os.path.join(self.base_dir, 'ptheoryequation.jpg')

        self.header_logo_img: ImageTk.PhotoImage | None = None
        self.equation_img: ImageTk.PhotoImage | None = None

        self.current_series_list: list[dict] = []
        self.current_target_year: int | None = None
        self.results_text = tk.StringVar(
            value='Run a simulation to generate a chart explanation here.'
        )

        self.hover_outer = None
        self.hover_mid = None
        self.hover_core = None
        self.hover_label = None

        self._build_layout()
        self._build_chart()
        self._init_hover_artists()
        self._set_defaults()
        self.calculate_all_models(animated=False)

    ## Asset helpers
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

    ## Layout
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
        card = tk.Frame(
            parent,
            bg=self.panel,
            padx=12,
            pady=12,
            highlightbackground=self.border,
            highlightthickness=1,
        )
        card.pack(fill='x', pady=(0, 12))

        tk.Label(
            card,
            text=title,
            bg=self.panel,
            fg=self.neon,
            font=('Segoe UI', 10, 'bold'),
        ).pack(anchor='w', pady=(0, 8))
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

        tk.Label(
            brand_wrap,
            text='BitcoinVersus.Tech',
            bg=self.bg,
            fg=self.neon,
            font=('Segoe UI', 18, 'bold'),
        ).pack(anchor='w')

        tk.Label(
            brand_wrap,
            text='Power Efficiency Theory Simulator',
            bg=self.bg,
            fg=self.muted,
            font=('Segoe UI', 10),
        ).pack(anchor='w')

        outer = tk.Frame(self.control_frame, bg=self.bg, padx=16)
        outer.pack(fill='x')

        equation_box = tk.Frame(
            outer,
            bg=self.panel,
            padx=8,
            pady=8,
            highlightbackground=self.border,
            highlightthickness=1,
        )
        equation_box.pack(fill='x', pady=(0, 12))

        self.equation_img = self._load_tk_image(self.equation_path, (390, 74))
        if self.equation_img is not None:
            tk.Label(
                equation_box,
                image=self.equation_img,
                bg=self.panel,
                bd=0,
                highlightthickness=0,
            ).pack(anchor='center')
        else:
            tk.Label(
                equation_box,
                text='Equation image not found',
                bg=self.panel,
                fg=self.muted,
                font=('Segoe UI', 11),
            ).pack(anchor='center')

        ## Power Efficiency Simulator module
        model_module = tk.Frame(
            outer,
            bg=self.panel,
            padx=12,
            pady=12,
            highlightbackground=self.border,
            highlightthickness=1,
        )
        model_module.pack(fill='x', pady=(0, 12))

        model_header = tk.Frame(model_module, bg=self.panel)
        model_header.pack(fill='x', pady=(0, 8))

        tk.Label(
            model_header,
            text='POWER EFFICIENCY SIMULATOR',
            bg=self.panel,
            fg=self.neon,
            font=('Segoe UI', 11, 'bold'),
        ).pack(side='left')

        tk.Button(
            model_header,
            text='+',
            command=self.add_model_widget,
            bg=self.panel_2,
            fg=self.neon,
            activebackground=self.panel,
            activeforeground=self.neon,
            relief='flat',
            bd=0,
            font=('Segoe UI', 12, 'bold'),
            width=3,
            cursor='hand2',
            highlightbackground=self.border,
            highlightthickness=1,
        ).pack(side='right')

        self.models_container = tk.Frame(model_module, bg=self.panel)
        self.models_container.pack(fill='x')
        self.add_model_widget(initial=True)

        model_note = (
            'Enter the variables for one or more price scenarios. The simulator uses '
            'starting value, power growth, efficiency improvement, lag, and lag decay '
            'to compare how different assumptions change the projected Bitcoin value curve over time.'
        )
        tk.Label(
            model_module,
            text=model_note,
            bg=self.panel,
            fg=self.muted,
            justify='left',
            wraplength=370,
            font=('Segoe UI', 9),
        ).pack(anchor='w', pady=(8, 0))

        model_buttons = tk.Frame(outer, bg=self.bg)
        model_buttons.pack(fill='x', pady=(0, 12))

        tk.Button(
            model_buttons,
            text='Calculate Model(s)',
            command=self.calculate_all_models,
            bg=self.neon,
            fg='#000000',
            activebackground='#7dff63',
            activeforeground='#000000',
            relief='flat',
            bd=0,
            font=('Segoe UI', 10, 'bold'),
            padx=16,
            pady=8,
            cursor='hand2',
        ).pack(side='left')

        tk.Button(
            model_buttons,
            text='Reset Model(s)',
            command=self._reset_models_and_refresh,
            bg=self.panel,
            fg=self.neon,
            activebackground=self.panel_2,
            activeforeground=self.neon,
            relief='flat',
            bd=0,
            font=('Segoe UI', 10),
            padx=16,
            pady=8,
            cursor='hand2',
            highlightbackground=self.border,
            highlightthickness=1,
        ).pack(side='left', padx=(8, 0))

        ## ASIC Machine Mining Metrics Simulator module
        machine_module = tk.Frame(
            outer,
            bg=self.panel,
            padx=12,
            pady=12,
            highlightbackground=self.border,
            highlightthickness=1,
        )
        machine_module.pack(fill='x', pady=(0, 12))

        machine_header = tk.Frame(machine_module, bg=self.panel)
        machine_header.pack(fill='x', pady=(0, 8))

        tk.Label(
            machine_header,
            text='ASIC MACHINE MINING METRICS SIMULATOR',
            bg=self.panel,
            fg=self.neon,
            font=('Segoe UI', 10, 'bold'),
        ).pack(side='left')

        tk.Button(
            machine_header,
            text='+',
            command=self.add_machine_widget,
            bg=self.panel_2,
            fg=self.neon,
            activebackground=self.panel,
            activeforeground=self.neon,
            relief='flat',
            bd=0,
            font=('Segoe UI', 12, 'bold'),
            width=3,
            cursor='hand2',
            highlightbackground=self.border,
            highlightthickness=1,
        ).pack(side='right')

        self.machine_container = tk.Frame(machine_module, bg=self.panel)
        self.machine_container.pack(fill='x')
        self.add_machine_widget(initial=True)

        machine_note = (
            'Enter a start J/TH and an end J/TH across two years. The simulator '
            'will infer the annual efficiency improvement rate automatically. You '
            'can either type End J/TH directly or let the app derive it from watts and TH/s. '
            'You can now add multiple machine modules for side by side curve comparison.'
        )
        tk.Label(
            machine_module,
            text=machine_note,
            bg=self.panel,
            fg=self.muted,
            justify='left',
            wraplength=370,
            font=('Segoe UI', 9),
        ).pack(anchor='w', pady=(8, 0))

        machine_buttons = tk.Frame(outer, bg=self.bg)
        machine_buttons.pack(fill='x', pady=(0, 12))

        tk.Button(
            machine_buttons,
            text='Calculate Machine',
            command=self.calculate_from_mining_inputs,
            bg=self.neon,
            fg='#000000',
            activebackground='#7dff63',
            activeforeground='#000000',
            relief='flat',
            bd=0,
            font=('Segoe UI', 10, 'bold'),
            padx=16,
            pady=8,
            cursor='hand2',
        ).pack(side='left')

        tk.Button(
            machine_buttons,
            text='Reset Machine',
            command=self._reset_machine_and_refresh,
            bg=self.panel,
            fg=self.neon,
            activebackground=self.panel_2,
            activeforeground=self.neon,
            relief='flat',
            bd=0,
            font=('Segoe UI', 10),
            padx=16,
            pady=8,
            cursor='hand2',
            highlightbackground=self.border,
            highlightthickness=1,
        ).pack(side='left', padx=(8, 0))

        info_card = self._card(outer, 'DEFINITION')
        info_text = (
            'Power Efficiency Theory is a concept that measures the J/TH '
            'and hashrate improvement of Bitcoin mining systems over time and uses those '
            'changes to form a relative idea of Bitcoin value based on measurable '
            'computational energy productivity metrics.'
        )
        tk.Label(
            info_card,
            text=info_text,
            bg=self.panel,
            fg=self.muted,
            justify='left',
            wraplength=370,
            font=('Segoe UI', 10),
        ).pack(anchor='w')

    ## Scenario widgets
    def add_model_widget(self, initial: bool = False) -> None:
        if len(self.model_scenarios) >= 5:
            if not initial:
                messagebox.showinfo('Limit Reached', 'You can compare up to 5 model widgets at once.')
            return

        index = len(self.model_scenarios) + 1

        card = tk.Frame(
            self.models_container,
            bg=self.panel,
            padx=12,
            pady=12,
            highlightbackground=self.border,
            highlightthickness=0,
        )
        card.pack(fill='x', pady=(0, 12))

        title_row = tk.Frame(card, bg=self.panel)
        title_row.pack(fill='x', pady=(0, 8))

        tk.Label(
            title_row,
            text=f'Scenario {index}',
            bg=self.panel,
            fg=self.neon,
            font=('Segoe UI', 10, 'bold'),
        ).pack(side='left')

        if index > 1:
            tk.Button(
                title_row,
                text='−',
                command=lambda c=card: self.remove_model_widget(c),
                bg=self.panel_2,
                fg=self.neon,
                activebackground=self.panel,
                activeforeground=self.neon,
                relief='flat',
                bd=0,
                font=('Segoe UI', 11, 'bold'),
                width=3,
                cursor='hand2',
                highlightbackground=self.border,
                highlightthickness=1,
            ).pack(side='right')

        fields: dict[str, tk.StringVar] = {}
        for label_text, key in [
            ('Start Value V0', 'V0'),
            ('Power Growth p', 'p'),
            ('Efficiency Improvement e', 'e'),
            ('Initial Lag L', 'L0'),
            ('Lag Decay d', 'd'),
            ('Start Year', 'start_year'),
            ('End Year', 'end_year'),
        ]:
            row = tk.Frame(card, bg=self.panel)
            row.pack(fill='x', pady=4)

            tk.Label(
                row,
                text=label_text,
                bg=self.panel,
                fg=self.neon,
                font=('Segoe UI', 10),
                width=18,
                anchor='w',
            ).pack(side='left')

            var = tk.StringVar()
            entry = tk.Entry(
                row,
                textvariable=var,
                bg=self.panel_2,
                fg=self.neon,
                insertbackground=self.neon,
                relief='flat',
                bd=0,
                highlightthickness=1,
                highlightbackground=self.border,
                highlightcolor=self.neon,
                width=18,
                font=('Consolas', 10),
            )
            entry.pack(side='left', padx=(8, 0), ipady=5)
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
        self._refresh_scenario_titles()
        self.calculate_all_models(animated=False)

    def _refresh_scenario_titles(self) -> None:
        for idx, card in enumerate(self.model_cards, start=1):
            title_row = card.winfo_children()[0]
            title_label = title_row.winfo_children()[0]
            if isinstance(title_label, tk.Label):
                title_label.config(text=f'Scenario {idx}')

    ## Machine widgets
    def add_machine_widget(self, initial: bool = False) -> None:
        if len(self.machine_scenarios) >= 5:
            if not initial:
                messagebox.showinfo('Limit Reached', 'You can compare up to 5 machine widgets at once.')
            return

        index = len(self.machine_scenarios) + 1

        card = tk.Frame(
            self.machine_container,
            bg=self.panel,
            padx=12,
            pady=12,
            highlightbackground=self.border,
            highlightthickness=0,
        )
        card.pack(fill='x', pady=(0, 12))

        title_row = tk.Frame(card, bg=self.panel)
        title_row.pack(fill='x', pady=(0, 8))

        tk.Label(
            title_row,
            text=f'Machine {index}',
            bg=self.panel,
            fg=self.neon,
            font=('Segoe UI', 10, 'bold'),
        ).pack(side='left')

        if index > 1:
            tk.Button(
                title_row,
                text='−',
                command=lambda c=card: self.remove_machine_widget(c),
                bg=self.panel_2,
                fg=self.neon,
                activebackground=self.panel,
                activeforeground=self.neon,
                relief='flat',
                bd=0,
                font=('Segoe UI', 11, 'bold'),
                width=3,
                cursor='hand2',
                highlightbackground=self.border,
                highlightthickness=1,
            ).pack(side='right')

        fields: dict[str, tk.StringVar] = {}
        for label_text, key in [
            ('Start Year', 'metric_start_year'),
            ('Start J/TH', 'start_jth'),
            ('End Year', 'metric_end_year'),
            ('End J/TH', 'end_jth'),
            ('End Machine Watts', 'watts'),
            ('End Hashrate TH/s', 'hashrate_th'),
        ]:
            row = tk.Frame(card, bg=self.panel)
            row.pack(fill='x', pady=4)

            tk.Label(
                row,
                text=label_text,
                bg=self.panel,
                fg=self.neon,
                font=('Segoe UI', 10),
                width=18,
                anchor='w',
            ).pack(side='left')

            var = tk.StringVar()
            entry = tk.Entry(
                row,
                textvariable=var,
                bg=self.panel_2,
                fg=self.neon,
                insertbackground=self.neon,
                relief='flat',
                bd=0,
                highlightthickness=1,
                highlightbackground=self.border,
                highlightcolor=self.neon,
                width=18,
                font=('Consolas', 10),
            )
            entry.pack(side='left', padx=(8, 0), ipady=5)
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
        self._refresh_machine_titles()
        self.calculate_all_models(animated=False)

    def _refresh_machine_titles(self) -> None:
        for idx, card in enumerate(self.machine_cards, start=1):
            title_row = card.winfo_children()[0]
            title_label = title_row.winfo_children()[0]
            if isinstance(title_label, tk.Label):
                title_label.config(text=f'Machine {idx}')

    ## Metrics
    def _build_metrics(self) -> None:
        metrics_frame = tk.Frame(self.chart_shell, bg=self.bg)
        metrics_frame.grid(row=0, column=0, sticky='ew', pady=(0, 10))

        for i in range(9):
            metrics_frame.grid_columnconfigure(i, weight=1)

        metric_defs = [
            ('Final Value', 'final_value'),
            ('Growth Multiple', 'growth_multiple'),
            ('Growth Ratio', 'growth_ratio'),
            ('Derived J/TH', 'derived_jth'),
            ('Efficiency Rate', 'eff_delta'),
            ('Target Year Value', 'target_value'),
            ('Years Modeled', 'years_modeled'),
            ('Implied End J/TH', 'implied_end_jth'),
            ('Implied End TH/s', 'implied_end_hashrate'),
        ]

        for col, (label, key) in enumerate(metric_defs):
            card = tk.Frame(
                metrics_frame,
                bg=self.panel,
                padx=10,
                pady=8,
                highlightbackground=self.border,
                highlightthickness=1,
            )
            card.grid(row=0, column=col, sticky='nsew', padx=(0 if col == 0 else 6, 0))

            self.metric_vars[key] = tk.StringVar(value='--')

            tk.Label(
                card,
                text=label,
                bg=self.panel,
                fg=self.muted,
                font=('Segoe UI', 8),
            ).pack(anchor='w')

            tk.Label(
                card,
                textvariable=self.metric_vars[key],
                bg=self.panel,
                fg=self.neon,
                font=('Consolas', 10, 'bold'),
            ).pack(anchor='w', pady=(4, 0))

    def _build_results_box(self) -> None:
        controls_row = tk.Frame(self.chart_shell, bg=self.bg)
        controls_row.grid(row=2, column=0, sticky='ew', pady=(10, 8))
        controls_row.grid_columnconfigure(1, weight=1)

        tk.Button(
            controls_row,
            text='Download Chart',
            command=self._download_chart,
            bg=self.panel,
            fg=self.neon,
            activebackground=self.panel_2,
            activeforeground=self.neon,
            relief='flat',
            bd=0,
            font=('Segoe UI', 10, 'bold'),
            padx=16,
            pady=8,
            cursor='hand2',
            highlightbackground=self.border,
            highlightthickness=1,
        ).grid(row=0, column=0, sticky='w')

        results_card = tk.Frame(
            self.chart_shell,
            bg=self.panel,
            padx=12,
            pady=12,
            highlightbackground=self.border,
            highlightthickness=1,
        )
        results_card.grid(row=3, column=0, sticky='ew')

        tk.Label(
            results_card,
            text='RESULTS EXPLANATION',
            bg=self.panel,
            fg=self.neon,
            font=('Segoe UI', 10, 'bold'),
        ).pack(anchor='w', pady=(0, 6))

        tk.Label(
            results_card,
            textvariable=self.results_text,
            bg=self.panel,
            fg=self.muted,
            justify='left',
            wraplength=860,
            font=('Segoe UI', 9),
        ).pack(anchor='w')

    ## Chart
    def _build_chart(self) -> None:
        chart_frame = tk.Frame(
            self.chart_shell,
            bg=self.panel,
            padx=8,
            pady=8,
            highlightbackground=self.border,
            highlightthickness=1,
        )
        chart_frame.grid(row=1, column=0, sticky='nsew')
        chart_frame.grid_rowconfigure(0, weight=1)
        chart_frame.grid_columnconfigure(0, weight=1)

        self.figure = Figure(figsize=(8.2, 4.9), dpi=125, facecolor=self.panel)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor(self.panel)

        self.canvas = FigureCanvasTkAgg(self.figure, master=chart_frame)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky='nsew')

        self.canvas.mpl_connect('motion_notify_event', self._on_chart_hover)
        self.canvas.mpl_connect('figure_leave_event', self._on_chart_leave)

    def _init_hover_artists(self) -> None:
        self.hover_outer = self.ax.scatter(
            [], [], s=420, facecolors='none', edgecolors=self.neon,
            linewidths=1.2, alpha=0.10, zorder=10, visible=False
        )
        self.hover_mid = self.ax.scatter(
            [], [], s=180, facecolors='none', edgecolors=self.neon,
            linewidths=1.2, alpha=0.28, zorder=11, visible=False
        )
        self.hover_core = self.ax.scatter(
            [], [], s=28, color=self.neon, alpha=0.95, zorder=12, visible=False
        )
        self.hover_label = self.ax.annotate(
            '',
            xy=(0, 0),
            xytext=(12, 12),
            textcoords='offset points',
            color=self.neon,
            fontsize=8,
            fontname='Consolas',
            bbox=dict(boxstyle='round,pad=0.22', fc=self.panel_2, ec=self.border, alpha=0.94),
            visible=False,
        )

    ## Defaults
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
            card = self.model_cards.pop()
            self.model_scenarios.pop()
            card.destroy()

        if not self.model_scenarios:
            self.add_model_widget(initial=True)

        self._apply_model_defaults(self.model_scenarios[0], 0)
        self._refresh_scenario_titles()

    def _reset_machine_inputs(self) -> None:
        while len(self.machine_cards) > 1:
            card = self.machine_cards.pop()
            self.machine_scenarios.pop()
            card.destroy()

        if not self.machine_scenarios:
            self.add_machine_widget(initial=True)

        self._apply_machine_defaults(self.machine_scenarios[0], 0)
        self._refresh_machine_titles()

    def _reset_machine_and_refresh(self) -> None:
        self._reset_machine_inputs()
        self.calculate_all_models(animated=False)

    def _reset_models_and_refresh(self) -> None:
        self._reset_models()
        self.calculate_all_models(animated=False)

    ## Math
    def _build_price_series(
        self,
        v0: float,
        p: float,
        e: float,
        l0: float,
        d: float,
        start_year: int,
        end_year: int,
    ) -> dict:
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

        return {
            'years': years,
            'raw_values': values,
            'values_m': values / 1e6,
            'growth': growth,
        }

    def _collect_model_series(self) -> list[dict]:
        parsed = []
        for idx, fields in enumerate(self.model_scenarios, start=1):
            v0 = float(fields['V0'].get())
            p = float(fields['p'].get())
            e = float(fields['e'].get())
            l0 = float(fields['L0'].get())
            d = float(fields['d'].get())
            start_year = int(fields['start_year'].get())
            end_year = int(fields['end_year'].get())

            series = self._build_price_series(v0, p, e, l0, d, start_year, end_year)
            series['label'] = f'P Theory Scenario {idx}'
            series['color'] = self.default_line_colors[idx - 1]
            parsed.append(series)

        return parsed

    def _collect_machine_series(self, scenario_series: list[dict]) -> tuple[list[dict], dict | None]:
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
                    raise ValueError(
                        f'Machine {idx}: provide either End J/TH or both End Machine Watts and End Hashrate TH/s.'
                    )
                end_jth = float(end_jth_text)
                watts = float(watts_text) if watts_text else 3500.0
                hashrate_th = watts / end_jth

            if end_jth <= 0:
                raise ValueError(f'Machine {idx}: end J/TH must be greater than 0.')

            years_elapsed = metric_end_year - metric_start_year
            annual_eff_improvement = 1 - (end_jth / start_jth) ** (1 / years_elapsed)

            if annual_eff_improvement >= 1:
                raise ValueError(f'Machine {idx}: derived efficiency rate is invalid.')
            if annual_eff_improvement < 0:
                raise ValueError(
                    f'Machine {idx}: end J/TH is worse than start J/TH, which implies negative efficiency improvement.'
                )

            series = self._build_price_series(
                v0=v0,
                p=p,
                e=annual_eff_improvement,
                l0=l0,
                d=d,
                start_year=metric_start_year,
                end_year=metric_end_year,
            )
            series['label'] = f'Machine {idx} Derived Curve ({annual_eff_improvement:.2%}/yr)'
            series['color'] = self.machine_curve_color if idx == 1 else self.default_line_colors[(idx - 1) % len(self.default_line_colors)]
            machine_series_list.append(series)

            if idx == 1:
                first_machine_summary = {
                    'metric_start_year': metric_start_year,
                    'metric_end_year': metric_end_year,
                    'start_jth': start_jth,
                    'end_jth': end_jth,
                    'watts': watts,
                    'hashrate_th': hashrate_th,
                    'annual_eff_improvement': annual_eff_improvement,
                    'series': series,
                }

        return machine_series_list, first_machine_summary

    ## Calculations
    def calculate_all_models(self, animated: bool = True) -> None:
        try:
            parsed = self._collect_model_series()
        except ValueError as exc:
            messagebox.showerror('Invalid Input', str(exc))
            return

        self.machine_series_active = False
        self.last_years = parsed[0]['years']
        self.last_raw_values = [item['raw_values'] for item in parsed]
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
        if self.machine_scenarios:
            watts_text = self.machine_scenarios[0].get('watts', tk.StringVar(value='')).get().strip()
            if watts_text:
                baseline_watts = float(watts_text)

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

        machine_note = ''
        if len(self.machine_scenarios) > 1:
            machine_note = f' There are also {len(self.machine_scenarios)} machine modules available for separate machine curve comparisons.'

        self.results_text.set(
            f"Scenario 1 projects a final value of ${first['raw_values'][-1]:,.0f} "
            f"across {len(first['years']) - 1} modeled years, with a compounded growth "
            f"ratio of {first['growth']:.4f}. Based on an annual efficiency improvement rate "
            f"of {e:.2%}, the simulator also implies a machine improvement from 9.50 J/TH at "
            f"the start to {implied_end_jth:,.2f} J/TH by {end_year}. Using an assumed "
            f"baseline power draw of {baseline_watts:,.0f} watts, that corresponds to an "
            f"implied year end hashrate of {implied_end_hashrate:,.0f} TH/s.{machine_note} "
            f"Hover over any line to inspect specific year values."
        )

        self._render_chart(parsed, animated=animated, target_year=None)

    def calculate_from_mining_inputs(self) -> None:
        if not self.model_scenarios:
            return

        try:
            scenario_series = self._collect_model_series()
            machine_series_list, first_machine_summary = self._collect_machine_series(scenario_series)
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
        self.metric_vars['growth_multiple'].set(
            f"{(first_series['raw_values'][-1] / first_series['raw_values'][0]):,.2f}x"
        )
        self.metric_vars['growth_ratio'].set(f"{first_series['growth']:.4f}")
        self.metric_vars['years_modeled'].set(str(first_machine_summary['metric_end_year'] - first_machine_summary['metric_start_year']))
        self.metric_vars['implied_end_jth'].set('--')
        self.metric_vars['implied_end_hashrate'].set('--')

        extra_machine_note = ''
        if len(machine_series_list) > 1:
            extra_machine_note = (
                f" A total of {len(machine_series_list)} machine derived curves were plotted. "
                f"The top metrics summarize Machine 1."
            )

        self.results_text.set(
            f"Machine 1 inferred an annual efficiency improvement rate of "
            f"{first_machine_summary['annual_eff_improvement']:.2%} from "
            f"{first_machine_summary['start_jth']:.2f} J/TH in {first_machine_summary['metric_start_year']} "
            f"to {first_machine_summary['end_jth']:.2f} J/TH in {first_machine_summary['metric_end_year']}. "
            f"Using Scenario 1 as the base structure for V0, power growth, lag, and lag decay, "
            f"the machine derived curve projects a final value of ${first_series['raw_values'][-1]:,.0f}. "
            f"At {first_machine_summary['watts']:,.0f} watts, the end state machine corresponds to roughly "
            f"{first_machine_summary['hashrate_th']:,.0f} TH/s.{extra_machine_note}"
        )

        self._render_chart(all_series, animated=False, target_year=first_machine_summary['metric_end_year'])

    ## Chart rendering
    def _render_chart(self, series_list: list[dict], animated: bool = True, target_year: int | None = None) -> None:
        if self.chart_animation is not None and getattr(self.chart_animation, 'event_source', None) is not None:
            self.chart_animation.event_source.stop()
            self.chart_animation = None

        self.ax.clear()
        self.ax.set_facecolor(self.panel)
        self.ax.set_title(
            'Power Efficiency Compounding Scenarios',
            color=self.neon,
            fontsize=15,
            pad=16,
            fontname='Segoe UI',
            fontweight='bold',
        )
        self.ax.set_xlabel('Year', color=self.neon, fontsize=10, fontname='Segoe UI')
        self.ax.set_ylabel('Millions USD', color=self.neon, fontsize=10, fontname='Segoe UI')
        self.ax.tick_params(colors=self.neon, labelsize=9)
        self.ax.grid(True, color=self.neon, alpha=0.08, linewidth=0.7)
        self.ax.margins(x=0.03, y=0.12)

        for spine in self.ax.spines.values():
            spine.set_color(self.border)
            spine.set_linewidth(1.1)

        if not animated or len(series_list) > 1:
            self._draw_static_chart(series_list, target_year=target_year)
            self._init_hover_artists()
            self.canvas.draw_idle()
            return

        series = series_list[0]
        years = series['years']
        values_m = series['values_m']
        color = series['color']
        label = series['label']

        glow_1, = self.ax.plot([], [], color=color, linewidth=8, alpha=0.08)
        glow_2, = self.ax.plot([], [], color=color, linewidth=4, alpha=0.16)
        main_line, = self.ax.plot([], [], color=color, linewidth=2.6, label=label)
        area = [None]

        def animate(frame: int):
            idx = max(2, frame)
            x_data = years[:idx]
            y_data = values_m[:idx]
            glow_1.set_data(x_data, y_data)
            glow_2.set_data(x_data, y_data)
            main_line.set_data(x_data, y_data)

            if area[0] is not None:
                area[0].remove()
            area[0] = self.ax.fill_between(x_data, y_data, 0, color=color, alpha=0.08)

            if idx >= len(years):
                self._add_annotations(series_list, target_year=target_year)
                self._init_hover_artists()

            return glow_1, glow_2, main_line

        self.chart_animation = FuncAnimation(
            self.figure,
            animate,
            frames=len(years) + 1,
            interval=85,
            blit=False,
            repeat=False,
        )
        self.canvas.draw_idle()

    def _draw_static_chart(self, series_list: list[dict], target_year: int | None = None) -> None:
        for series in series_list:
            years = series['years']
            values_m = series['values_m']
            color = series['color']
            label = series['label']
            self.ax.plot(years, values_m, color=color, linewidth=5, alpha=0.10)
            self.ax.plot(years, values_m, color=color, linewidth=2.8, label=label)

        self._add_annotations(series_list, target_year=target_year)

    def _add_annotations(self, series_list: list[dict], target_year: int | None = None) -> None:
        primary = series_list[-1] if self.machine_series_active and len(series_list) > 1 else series_list[0]
        years = primary['years']
        values_m = primary['values_m']
        raw_values = primary['raw_values']
        color = primary['color']
        ymax = float(values_m.max()) if len(values_m) else 1.0

        milestone_years = [2030, 2035, 2040, 2045]
        for year in milestone_years:
            if year in years:
                idx = np.where(years == year)[0][0]
                val_m = values_m[idx]
                self.ax.scatter(year, val_m, color=color, s=24, zorder=5)
                self.ax.scatter(year, val_m, color=color, s=130, alpha=0.10, zorder=4)
                self.ax.annotate(
                    f'${raw_values[idx]:,.0f}',
                    xy=(year, val_m),
                    xytext=(0, 10 if val_m < ymax * 0.82 else -18),
                    textcoords='offset points',
                    color=self.neon,
                    fontsize=7,
                    ha='center',
                    fontname='Consolas',
                    bbox=dict(boxstyle='round,pad=0.16', fc=self.panel_2, ec=self.border, alpha=0.88),
                )

        final_x = years[-1]
        final_y = values_m[-1]
        self.ax.scatter(final_x, final_y, color=color, s=36, zorder=6)
        self.ax.scatter(final_x, final_y, color=color, s=180, alpha=0.10, zorder=5)
        self.ax.annotate(
            f'Final: ${raw_values[-1]:,.0f}',
            xy=(final_x, final_y),
            xytext=(-110, 14),
            textcoords='offset points',
            color=self.neon,
            fontsize=8,
            fontname='Consolas',
            bbox=dict(boxstyle='round,pad=0.22', fc=self.panel_2, ec=self.border, alpha=0.96),
            arrowprops=dict(arrowstyle='-', color=self.neon, lw=1.0),
        )

        if target_year is not None and target_year in years:
            idx = np.where(years == target_year)[0][0]
            target_y = values_m[idx]
            self.ax.scatter(target_year, target_y, color='#ffb347', s=48, zorder=7)
            self.ax.scatter(target_year, target_y, color='#ffb347', s=190, alpha=0.10, zorder=6)
            self.ax.annotate(
                f'Target {target_year}: ${raw_values[idx]:,.0f}',
                xy=(target_year, target_y),
                xytext=(18, -26),
                textcoords='offset points',
                color='#ffb347',
                fontsize=8,
                fontname='Consolas',
                bbox=dict(boxstyle='round,pad=0.22', fc=self.panel_2, ec=self.border, alpha=0.96),
                arrowprops=dict(arrowstyle='-', color='#ffb347', lw=1.0),
            )

        legend = self.ax.legend(facecolor=self.panel_2, edgecolor=self.border, fontsize=8, loc='upper left')
        for text in legend.get_texts():
            text.set_color(self.neon)

    ## Save chart
    def _download_chart(self) -> None:
        filepath = filedialog.asksaveasfilename(
            title='Save Chart As',
            defaultextension='.png',
            filetypes=[('PNG files', '*.png')],
            initialfile='power_efficiency_chart.png',
        )
        if not filepath:
            return

        try:
            self.figure.savefig(
                filepath,
                dpi=180,
                facecolor=self.figure.get_facecolor(),
                bbox_inches='tight',
            )
            messagebox.showinfo('Chart Saved', f'Chart saved to:\n{filepath}')
        except Exception as exc:
            messagebox.showerror('Save Failed', str(exc))

    ## Hover radar
    def _hide_hover_artists(self) -> None:
        if self.hover_outer is not None:
            self.hover_outer.set_visible(False)
        if self.hover_mid is not None:
            self.hover_mid.set_visible(False)
        if self.hover_core is not None:
            self.hover_core.set_visible(False)
        if self.hover_label is not None:
            self.hover_label.set_visible(False)

    def _set_scatter_offsets(self, scatter, x: float, y: float) -> None:
        scatter.set_offsets(np.array([[x, y]]))

    def _on_chart_leave(self, _event) -> None:
        self._hide_hover_artists()
        self.canvas.draw_idle()

    def _on_chart_hover(self, event) -> None:
        if event.inaxes != self.ax or event.xdata is None or event.ydata is None or not self.current_series_list:
            self._hide_hover_artists()
            self.canvas.draw_idle()
            return

        closest = None
        best_dist = float('inf')

        for series in self.current_series_list:
            years = series['years']
            vals = series['values_m']
            raw_vals = series['raw_values']
            color = series['color']
            label = series['label']

            idx = int(np.argmin(np.abs(years - event.xdata)))
            x = float(years[idx])
            y = float(vals[idx])

            dx = abs(event.xdata - x)
            dy = abs(event.ydata - y)
            dist = dx + (dy * 0.55)

            if dist < best_dist:
                best_dist = dist
                closest = (x, y, raw_vals[idx], color, label)

        if closest is None or best_dist > 1.4:
            self._hide_hover_artists()
            self.canvas.draw_idle()
            return

        x, y, raw_value, color, label = closest

        self.hover_outer.set_edgecolor(color)
        self.hover_mid.set_edgecolor(color)
        self.hover_core.set_color(color)

        self._set_scatter_offsets(self.hover_outer, x, y)
        self._set_scatter_offsets(self.hover_mid, x, y)
        self._set_scatter_offsets(self.hover_core, x, y)

        self.hover_outer.set_visible(True)
        self.hover_mid.set_visible(True)
        self.hover_core.set_visible(True)

        self.hover_label.xy = (x, y)
        self.hover_label.set_text(f'{label}\n{x:.0f}: ${raw_value:,.0f}')
        self.hover_label.set_visible(True)

        self.canvas.draw_idle()


def main() -> None:
    root = tk.Tk()
    PowerEfficiencySimulator(root)
    root.mainloop()


if __name__ == '__main__':
    main()