"""Offline Tk GUI with asynchronous scientific jobs and shared validated configuration."""

from __future__ import annotations

import gc
import json
import logging
import os
import sys
import time
import tkinter as tk
import uuid
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import fields
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

import yaml

from bikeenergylab import BikeModel, Config, Route, __version__
from bikeenergylab.io import json_safe
from bikeenergylab.routes import route_from_config

from .onboarding import EXAMPLES, TUTORIAL, execute_example
from .strings import HELP, STRINGS


class Tooltip:
    """Short help shown on hover and keyboard focus."""

    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget, self.text, self.window = widget, text, None
        widget.bind("<Enter>", self.show)
        widget.bind("<FocusIn>", self.show)
        widget.bind("<Leave>", self.hide)
        widget.bind("<FocusOut>", self.hide)

    def show(self, event: Any = None) -> None:
        if self.window:
            return
        self.window = tk.Toplevel(self.widget)
        self.window.overrideredirect(True)
        self.window.geometry(f"+{self.widget.winfo_rootx() + 15}+{self.widget.winfo_rooty() + 25}")
        ttk.Label(self.window, text=self.text, padding=10, wraplength=450).pack()

    def hide(self, event: Any = None) -> None:
        if self.window:
            self.window.destroy()
            self.window = None


class Application:
    sections = [
        "home",
        "bike",
        "rider",
        "motor",
        "battery",
        "route",
        "environment",
        "physics",
        "calibration",
        "hybrid",
        "uncertainty",
        "simulation",
        "experiments",
        "results",
        "export",
    ]

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("BikeEnergyLab — Scientific Framework")
        root.geometry("1160x800")
        root.minsize(950, 680)
        self.language = tk.StringVar(value="es")
        self.config = Config()
        self.config.route["speed_mps"] = 6.94
        self.current_route: Route | None = None
        self.last_result: Any = None
        self.hybrid_model: Any = None
        self.configuration_directory = Path.cwd()
        self.job = None
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.status = tk.StringVar()
        self.section = "home"
        self.variables: dict[str, tk.Variable] = {}
        self.result_widgets: list[tk.Text] = []
        self.closed = False
        self.disabled_controls = []
        self.example_key = EXAMPLES[0].key
        self.loaded_example_key: str | None = None
        self.tutorial_open = False
        self.tutorial_index = 0
        self.build()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def s(self, key: str) -> str:
        return STRINGS[self.language.get()][key]

    def build(self) -> None:
        for child in self.root.winfo_children():
            child.destroy()
        self.variables.clear()
        self.result_widgets.clear()
        toolbar = ttk.Frame(self.root, padding=12)
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="BikeEnergyLab", font=("Segoe UI", 19, "bold")).pack(side="left")
        ttk.Button(toolbar, text=self.s("load"), command=self.load_yaml).pack(
            side="left", padx=(25, 5)
        )
        ttk.Button(toolbar, text=self.s("save"), command=self.save_yaml).pack(side="left", padx=5)
        ttk.Button(toolbar, text=self.s("run"), command=self.run_simulation).pack(
            side="left", padx=5
        )
        ttk.Button(toolbar, text=self.s("examples"), command=self.show_examples).pack(
            side="left", padx=5
        )
        ttk.Button(toolbar, text=self.s("tutorial"), command=self.start_tutorial).pack(
            side="left", padx=5
        )
        selector = ttk.Combobox(
            toolbar, textvariable=self.language, values=["es", "en"], width=5, state="readonly"
        )
        selector.pack(side="right")
        selector.bind("<<ComboboxSelected>>", self.change_language)
        self.tutorial_frame = ttk.Frame(self.root, padding=(20, 8))
        if self.tutorial_open:
            self.tutorial_frame.pack(fill="x")
        self.render_tutorial()
        content = ttk.Frame(self.root)
        self.content = content
        content.pack(fill="both", expand=True, padx=12)
        self.navigation = ttk.Treeview(content, show="tree", selectmode="browse", height=20)
        self.navigation.column("#0", width=180, stretch=False)
        self.navigation.pack(side="left", fill="y")
        self.frames = {}
        self.section_wrappers = {}
        self.section_canvases = {}
        self.container = ttk.Frame(content, padding=20)
        self.container.pack(side="left", fill="both", expand=True)
        for section in self.sections:
            self.navigation.insert("", "end", iid=section, text=self.s(section))
            wrapper = ttk.Frame(self.container)
            canvas = tk.Canvas(wrapper, highlightthickness=0)
            scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side="right", fill="y")
            canvas.pack(side="left", fill="both", expand=True)
            inner = ttk.Frame(canvas)
            item = canvas.create_window((0, 0), window=inner, anchor="nw")
            inner.bind(
                "<Configure>", lambda event, c=canvas: c.configure(scrollregion=c.bbox("all"))
            )
            canvas.bind(
                "<Configure>", lambda event, c=canvas, i=item: c.itemconfigure(i, width=event.width)
            )
            self.frames[section] = inner
            self.section_wrappers[section] = wrapper
            self.section_canvases[section] = canvas
        self.root.bind_all("<MouseWheel>", self.scroll_section)
        self.navigation.bind("<<TreeviewSelect>>", self.select_section)
        self.build_examples()
        self.label("home", self.s("help"))
        self.label(
            "home",
            f"BikeEnergyLab {__version__}\n"
            "A Scientific Framework for Energy Consumption and Range Modeling of Electric Bicycles\n\n"
            "Francisco Javier Burgos Flórez\nJuan Guillermo Popayán Hernández\nfjburgosf@gmail.com",
        )
        for section in ["bike", "rider", "motor", "battery", "environment"]:
            self.parameter_form(section)
        self.label("physics", self.s("physics_help"))
        self.parameter_form("simulation")
        self.parameter_form("regeneration", self.frames["motor"])
        route_frame = self.frames["route"]
        self.route_values = {
            key: tk.StringVar(value=str(self.config.route.get(key, default)))
            for key, default in [("distance_m", 10000), ("speed_mps", 6.94), ("grade", 0)]
        }
        for row, (key, label) in enumerate(
            [("distance_m", "distance"), ("speed_mps", "speed"), ("grade", "grade")]
        ):
            ttk.Label(route_frame, text=self.s(label)).grid(row=row, column=0, sticky="w", pady=8)
            entry = ttk.Entry(route_frame, textvariable=self.route_values[key])
            entry.grid(row=row, column=1, padx=15)
            Tooltip(entry, self.s(label) + "\n" + self.s("assumption"))
        ttk.Button(route_frame, text=self.s("manual"), command=self.manual_route).grid(
            row=3, column=0, pady=12
        )
        ttk.Button(route_frame, text=self.s("csv"), command=lambda: self.import_route("csv")).grid(
            row=4, column=0, pady=8
        )
        ttk.Button(route_frame, text=self.s("gpx"), command=lambda: self.import_route("gpx")).grid(
            row=4, column=1, pady=8
        )
        ttk.Button(route_frame, text=self.s("preview"), command=self.preview_route).grid(
            row=5, column=0, pady=8
        )
        self.route_plot_frame = ttk.Frame(route_frame)
        self.route_plot_frame.grid(row=6, column=0, columnspan=2, sticky="nsew")
        self.label("calibration", self.s("data_help"))
        ttk.Button(self.frames["calibration"], text=self.s("calibrate"), command=self.fit_csv).pack(
            anchor="w", pady=15
        )
        ttk.Button(
            self.frames["calibration"], text=self.s("telemetry"), command=self.convert_telemetry
        ).pack(anchor="w", pady=8)
        self.label("hybrid", self.s("data_help"))
        ttk.Button(self.frames["hybrid"], text=self.s("learn"), command=self.learn_csv).pack(
            anchor="w", pady=12
        )
        ttk.Button(self.frames["hybrid"], text=self.s("demo"), command=self.learn_demo).pack(
            anchor="w", pady=12
        )
        ttk.Button(self.frames["hybrid"], text=self.s("load_model"), command=self.load_model).pack(
            anchor="w", pady=8
        )
        ttk.Button(self.frames["hybrid"], text=self.s("save_model"), command=self.save_model).pack(
            anchor="w", pady=8
        )
        ttk.Button(self.frames["hybrid"], text=self.s("adapt"), command=self.adapt_csv).pack(
            anchor="w", pady=8
        )
        ttk.Button(self.frames["hybrid"], text=self.s("intervals"), command=self.interval_csv).pack(
            anchor="w", pady=8
        )
        ttk.Button(
            self.frames["uncertainty"], text=self.s("probability"), command=self.run_uncertainty
        ).pack(anchor="w", pady=10)
        self.label("uncertainty", self.s("yaml_help"))
        self.yaml_editor = tk.Text(self.frames["uncertainty"], height=24, wrap="none")
        self.yaml_editor.pack(fill="both", expand=True)
        self.refresh_yaml()
        ttk.Button(self.frames["uncertainty"], text=self.s("apply"), command=self.apply_yaml).pack(
            anchor="w", pady=8
        )
        self.label("experiments", self.s("experiment_help"))
        ttk.Button(
            self.frames["experiments"], text=self.s("benchmark"), command=self.run_benchmark
        ).pack(anchor="w", pady=15)
        self.sensitivity_method = tk.StringVar(value="sobol")
        ttk.Combobox(
            self.frames["experiments"],
            textvariable=self.sensitivity_method,
            values=["oat", "spearman", "morris", "sobol"],
            state="readonly",
        ).pack(anchor="w")
        ttk.Button(
            self.frames["experiments"], text=self.s("sensitivity"), command=self.run_sensitivity
        ).pack(anchor="w", pady=8)
        ttk.Button(self.frames["experiments"], text=self.s("suite"), command=self.run_suite).pack(
            anchor="w", pady=8
        )
        self.plot_frame = ttk.Notebook(self.frames["results"], height=570)
        self.plot_frame.pack(fill="both", expand=True)
        self.details_frame = ttk.Frame(self.plot_frame)
        self.plot_frame.add(self.details_frame, text=self.s("details"))
        self.result_text = tk.Text(self.details_frame, wrap="word", height=24)
        text_scroll = ttk.Scrollbar(self.details_frame, command=self.result_text.yview)
        text_scroll.pack(side="right", fill="y")
        self.result_text.configure(yscrollcommand=text_scroll.set)
        self.result_text.pack(fill="both", expand=True)
        self.result_widgets.append(self.result_text)
        self.label("export", self.s("export_help"))
        ttk.Button(self.frames["export"], text=self.s("export_result"), command=self.export).pack(
            anchor="w", pady=15
        )
        ttk.Label(self.root, textvariable=self.status, padding=10).pack(fill="x")
        self.status.set(self.s("ready"))
        self.navigation.selection_set(self.section)
        self.show(self.section)
        if self.last_result is not None:
            self.display_result(self.last_result)
        gc.collect()  # Release obsolete Tk/Matplotlib cycles on their owning thread.

    def build_examples(self) -> None:
        card = ttk.LabelFrame(self.frames["home"], text=self.s("examples"), padding=15)
        card.pack(fill="x", pady=(0, 12))
        ttk.Label(card, text=self.s("examples_help"), wraplength=650).pack(anchor="w")
        labels = [example.text(self.language.get()) for example in EXAMPLES]
        self.example_selector = ttk.Combobox(card, values=labels, state="readonly", width=44)
        self.example_selector.current(
            next(i for i, e in enumerate(EXAMPLES) if e.key == self.example_key)
        )
        self.example_selector.pack(anchor="w", pady=10)
        self.example_selector.bind("<<ComboboxSelected>>", self.select_example)
        self.example_description = ttk.Label(card, wraplength=650, justify="left")
        self.example_description.pack(anchor="w", fill="x", pady=5)
        card.bind(
            "<Configure>",
            lambda event: self.example_description.configure(wraplength=max(200, event.width - 35)),
        )
        self.update_example_description()
        if self.loaded_example_key is not None:
            loaded = next(e for e in EXAMPLES if e.key == self.loaded_example_key)
            ttk.Label(
                card,
                text=f"{self.s('active_example')}: {loaded.text(self.language.get())}\n{self.s('simulate_example_help')}",
                wraplength=650,
                justify="left",
            ).pack(anchor="w", pady=5)
        buttons = ttk.Frame(card)
        buttons.pack(anchor="w", pady=10)
        ttk.Button(buttons, text=self.s("load_example"), command=self.load_example).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(card, text=self.s("start_tutorial"), command=self.start_tutorial).pack(
            anchor="w", pady=(4, 0)
        )

    def selected_example(self) -> Any:
        return next(example for example in EXAMPLES if example.key == self.example_key)

    def select_example(self, event: Any = None) -> None:
        self.example_key = EXAMPLES[self.example_selector.current()].key
        self.update_example_description()

    def update_example_description(self) -> None:
        self.example_description.configure(
            text=self.selected_example().text(self.language.get(), description=True)
        )

    def show_examples(self) -> None:
        self.navigation.selection_set("home")
        self.show("home")
        self.section_canvases["home"].yview_moveto(0)
        self.example_selector.focus_set()

    def load_example(self, key: str | None = None) -> None:
        if self.job is not None:
            return
        if key is not None:
            self.example_key = key
        example = self.selected_example()
        self.loaded_example_key = example.key
        self.config = example.configuration()
        self.configuration_directory = Path.cwd()
        self.current_route = route_from_config(self.config)
        self.hybrid_model = self.last_result = None
        self.section = "home"
        self.build()
        self.status.set(
            f"{self.s('example_loaded')}: {example.text(self.language.get())}. {self.s('simulate_example_help')}"
        )

    def run_example(self, key: str | None = None) -> None:
        if self.job is not None:
            return
        self.load_example(key)
        self.run_simulation()

    def start_tutorial(self) -> None:
        self.tutorial_open = True
        self.tutorial_index = 0
        self.tutorial_frame.pack(fill="x", before=self.content)
        self.render_tutorial(navigate=True)

    def close_tutorial(self) -> None:
        self.tutorial_open = False
        self.tutorial_frame.pack_forget()

    def render_tutorial(self, *, navigate: bool = False) -> None:
        for child in self.tutorial_frame.winfo_children():
            child.destroy()
        if not self.tutorial_open:
            return
        step = TUTORIAL[self.tutorial_index]
        language = self.language.get()
        title = f"{self.s('tutorial')} · {self.tutorial_index + 1}/{len(TUTORIAL)} — {step.text('titles', language)}"
        ttk.Label(self.tutorial_frame, text=title, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        description = ttk.Label(
            self.tutorial_frame,
            text=step.text("descriptions", language),
            wraplength=1000,
            justify="left",
        )
        description.pack(anchor="w", fill="x", pady=6)
        self.tutorial_frame.bind(
            "<Configure>",
            lambda event: description.configure(wraplength=max(250, event.width - 45)),
        )
        controls = ttk.Frame(self.tutorial_frame)
        controls.pack(anchor="w")
        ttk.Button(
            controls, text=step.text("buttons", language), command=self.tutorial_action
        ).pack(side="left", padx=(0, 15))
        ttk.Button(
            controls,
            text=self.s("previous"),
            command=lambda: self.move_tutorial(-1),
            state="disabled" if self.tutorial_index == 0 else "normal",
        ).pack(side="left")
        ttk.Button(
            controls,
            text=self.s("next"),
            command=lambda: self.move_tutorial(1),
            state="disabled" if self.tutorial_index == len(TUTORIAL) - 1 else "normal",
        ).pack(side="left", padx=6)
        ttk.Button(controls, text=self.s("close_tutorial"), command=self.close_tutorial).pack(
            side="left"
        )
        if navigate:
            self.navigation.selection_set(step.section)
            self.show(step.section)
            self.section_canvases[step.section].yview_moveto(0)

    def move_tutorial(self, direction: int) -> None:
        self.tutorial_index = max(0, min(len(TUTORIAL) - 1, self.tutorial_index + direction))
        self.render_tutorial(navigate=True)

    def tutorial_action(self) -> None:
        action = TUTORIAL[self.tutorial_index].action
        if action == "load":
            self.load_example("flat")
        elif action == "rider":
            self.navigation.selection_set("rider")
            self.show("rider")
        elif action == "preview":
            self.preview_route()
        elif action == "simulate":
            self.run_simulation()
        elif action == "results":
            if self.last_result is None:
                self.status.set(self.s("tutorial_needs_result"))
            else:
                self.navigation.selection_set("results")
                self.show("results")
                self.plot_frame.select(1 if len(self.plot_frame.tabs()) > 1 else 0)
        elif action == "uncertainty":
            self.run_example("uncertainty")
        elif action == "export":
            if self.last_result is None:
                self.status.set(self.s("tutorial_needs_result"))
            else:
                self.export()
        else:
            self.close_tutorial()

    def label(self, section: str, text: str) -> None:
        ttk.Label(self.frames[section], text=text, justify="left", wraplength=800).pack(
            anchor="w", pady=10
        )

    def parameter_form(self, section: str, parent: ttk.Frame | None = None) -> None:
        parent = parent or self.frames[section]
        form = ttk.Frame(parent)
        form.pack(anchor="nw", fill="x", pady=5)
        defaults = getattr(Config(), section)
        settings = getattr(self.config, section)
        row = 0
        for info in fields(settings):
            value = getattr(settings, info.name)
            if info.name not in HELP:
                continue  # Structured empirical curves/maps are configured through the YAML editor.
            key = f"{section}.{info.name}"
            unit, suggested_range, spanish, english = HELP[info.name]
            description = spanish if self.language.get() == "es" else english
            if key == "regeneration.efficiency":
                description = (
                    "Eficiencia de recuperación rueda → batería."
                    if self.language.get() == "es"
                    else "Wheel → battery regenerative conversion efficiency."
                )
            ttk.Label(form, text=f"{info.name} [{unit}]").grid(
                row=row, column=0, sticky="w", padx=5, pady=3
            )
            if isinstance(value, bool):
                variable = tk.BooleanVar(value=value)
                control = ttk.Checkbutton(form, variable=variable)
            else:
                variable = tk.StringVar(value="" if value is None else str(value))
                options = {
                    "mode": ["constant", "conditions"],
                    "model": ["energy", "soc", "ecm"],
                    "assist_mode": ["demand", "proportional"],
                }.get(info.name)
                control = (
                    ttk.Combobox(
                        form, textvariable=variable, values=options, state="readonly", width=19
                    )
                    if options
                    else ttk.Entry(form, textvariable=variable, width=22)
                )
            control.grid(row=row, column=1, padx=12, pady=3)
            self.variables[key] = variable
            hint = f"{description}\n{self.s('units')}: {unit}\n{self.s('range')}: {suggested_range}\n{self.s('default')}: {getattr(defaults, info.name)}\n{self.s('assumption')}"
            Tooltip(control, hint)
            ttk.Label(form, text=description, wraplength=480).grid(
                row=row, column=2, sticky="w", padx=5
            )
            row += 1

    def read_config(self) -> Config:
        values = self.config.to_dict()
        for path, variable in self.variables.items():
            section, key = path.split(".")
            previous = getattr(getattr(self.config, section), key)
            val = variable.get()
            if isinstance(previous, bool):
                converted = bool(val)
            elif isinstance(previous, str):
                converted = val
            else:
                converted = None if val == "" and key == "air_density_kgm3" else float(val)
            values[section][key] = converted
        self.config = Config.from_dict(values)
        return self.config

    def show(self, section: str) -> None:
        for frame in self.section_wrappers.values():
            frame.pack_forget()
        self.section_wrappers[section].pack(fill="both", expand=True)
        self.section = section

    def scroll_section(self, event: Any) -> None:
        if event.widget.winfo_class() not in {"Text", "Treeview", "TCombobox"}:
            self.section_canvases[self.section].yview_scroll(-int(event.delta / 120), "units")

    def draw_figure(self, figure: Any, parent: Any) -> None:
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

        canvas = FigureCanvasTkAgg(figure, parent)
        canvas.draw()
        NavigationToolbar2Tk(canvas, parent).update()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def preview_route(self) -> None:
        from .plots import route_figure

        try:
            for widget in self.route_plot_frame.winfo_children():
                widget.destroy()
            self.draw_figure(route_figure(self.route(), self.language.get()), self.route_plot_frame)
        except Exception as error:
            messagebox.showerror(self.s("error"), str(error))

    def select_section(self, event: Any = None) -> None:
        selected = self.navigation.selection()
        if selected:
            self.show(selected[0])

    def change_language(self, event: Any = None) -> None:
        try:
            self.read_config()
            self.build()
        except (ValueError, TypeError) as error:
            messagebox.showerror(self.s("error"), str(error))

    def refresh_yaml(self) -> None:
        self.yaml_editor.delete("1.0", "end")
        self.yaml_editor.insert(
            "1.0", yaml.safe_dump(self.config.to_dict(), sort_keys=False, allow_unicode=True)
        )

    def apply_yaml(self) -> None:
        try:
            self.config = Config.from_dict(yaml.safe_load(self.yaml_editor.get("1.0", "end")))
            self.current_route = None
            self.build()
        except (ValueError, TypeError, yaml.YAMLError) as error:
            messagebox.showerror(self.s("error"), str(error))

    def load_yaml(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("YAML", "*.yaml *.yml")])
        if path:
            try:
                self.config = Config.from_yaml(path)
                self.configuration_directory = Path(path).resolve().parent
                self.current_route = None
                self.loaded_example_key = None
                self.hybrid_model = None
                self.last_result = None
                self.build()
            except Exception as error:
                messagebox.showerror(self.s("error"), str(error))

    def save_yaml(self) -> None:
        try:
            cfg = self.read_config()
            path = filedialog.asksaveasfilename(
                defaultextension=".yaml", filetypes=[("YAML", "*.yaml")]
            )
            if path:
                Path(path).write_text(
                    yaml.safe_dump(cfg.to_dict(), sort_keys=False), encoding="utf-8"
                )
        except (ValueError, OSError) as error:
            messagebox.showerror(self.s("error"), str(error))

    def manual_route(self) -> None:
        try:
            options = {key: float(value.get()) for key, value in self.route_values.items()}
            self.current_route = Route.synthetic(**options)
            self.config.route = dict(kind="synthetic", **options)
            self.status.set(f"{self.s('route')}: {self.current_route.distance_m / 1000:.2f} km")
            self.refresh_yaml()
        except ValueError as error:
            messagebox.showerror(self.s("error"), str(error))

    def import_route(self, kind: str) -> None:
        path = filedialog.askopenfilename(filetypes=[(kind.upper(), f"*.{kind}")])
        if path:
            try:
                self.current_route = Route.from_csv(path) if kind == "csv" else Route.from_gpx(path)
                self.config.route = {"kind": kind, "path": path}
                self.status.set(f"{Path(path).name}: {self.current_route.distance_m / 1000:.2f} km")
                self.refresh_yaml()
            except Exception as error:
                messagebox.showerror(self.s("error"), str(error))

    def route(self) -> Route:
        return self.current_route or route_from_config(self.config)

    def submit(self, job: Callable[[], Any], callback: Callable[[Any], None] | None = None) -> None:
        if self.job is not None:
            self.status.set(self.s("busy"))
            return
        gc.collect()
        self.status.set(self.s("busy"))
        self.job = self.executor.submit(job)
        self.callback = callback or self.display_result
        self.disable_inputs(self.root)
        self.root.after(50, self.poll)

    def disable_inputs(self, parent: Any) -> None:
        for widget in parent.winfo_children():
            if isinstance(widget, (ttk.Button, ttk.Entry, ttk.Combobox, ttk.Checkbutton, tk.Text)):
                self.disabled_controls.append((widget, str(widget.cget("state"))))
                widget.configure(state="disabled")
            self.disable_inputs(widget)

    def restore_inputs(self) -> None:
        for widget, state in self.disabled_controls:
            if widget.winfo_exists():
                widget.configure(state=state)
        self.disabled_controls.clear()

    def poll(self) -> None:
        if self.closed or self.job is None:
            return
        if not self.job.done():
            self.root.after(50, self.poll)
            return
        try:
            value = self.job.result()
            self.restore_inputs()
            self.status.set(self.s("ready"))
            self.callback(value)
        except Exception as error:
            logging.getLogger(__name__).exception("Scientific job failed")
            messagebox.showerror(self.s("error"), str(error))
            self.status.set(self.s("error"))
        finally:
            self.restore_inputs()
            self.job = None

    def run_simulation(self) -> None:
        try:
            cfg, route = self.read_config(), self.route()
            hybrid = self.hybrid_model
            example = next((e for e in EXAMPLES if e.key == self.loaded_example_key), None)
            if example is not None and example.operation == "uncertainty":
                self.run_uncertainty()
                return
            if example is not None and (
                example.operation == "calibration"
                or (example.operation == "hybrid" and hybrid is None)
            ):

                def apply(value: Any) -> None:
                    self.config, self.hybrid_model = value.config, value.hybrid_model
                    self.last_result = value.result
                    self.build()

                self.submit(lambda: execute_example(example, cfg, route), apply)
                return

            def job() -> Any:
                result = BikeModel(cfg).simulate(route)
                return hybrid.annotate_simulation(result) if hybrid is not None else result

            self.submit(job)
        except Exception as error:
            messagebox.showerror(self.s("error"), str(error))

    def run_uncertainty(self) -> None:
        try:
            from bikeenergylab.uncertainty import monte_carlo

            cfg, route = self.read_config(), self.route()
            options = dict(cfg.uncertainty)
            artifact = options.pop("model_artifact", None)
            options.setdefault("n_samples", 100)
            options.setdefault("seed", cfg.experiment.get("seed", 42))
            hybrid = self.hybrid_model
            base_directory = self.configuration_directory

            def job() -> Any:
                from bikeenergylab.residual import CGPRAModel

                learned = hybrid
                if learned is None and artifact:
                    path = Path(artifact)
                    learned = CGPRAModel.load(path if path.is_absolute() else base_directory / path)
                return monte_carlo(cfg, route, hybrid_model=learned, **options)

            self.submit(job)
        except Exception as error:
            messagebox.showerror(self.s("error"), str(error))

    def run_benchmark(self) -> None:
        from bikeenergylab.experiments import run_benchmark

        try:
            cfg = self.read_config()
            self.submit(
                lambda: run_benchmark(
                    cfg,
                    **{
                        k: cfg.experiment[k]
                        for k in ["n_train", "n_calibration", "n_test"]
                        if k in cfg.experiment
                    },
                ),
                lambda path: self.display_result({"benchmark_directory": str(path)}),
            )
        except Exception as error:
            messagebox.showerror(self.s("error"), str(error))

    def fit_csv(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Observations", "*.csv")])
        if path:
            from bikeenergylab.calibration import calibrate
            from bikeenergylab.experiments.synthetic import observations_from_csv

            try:
                cfg = self.read_config()

                def job() -> Any:
                    observations = observations_from_csv(path, cfg)
                    return calibrate(cfg, observations), observations

                def apply(value: Any) -> None:
                    from bikeenergylab.experiments.synthetic import serialize_observations
                    from bikeenergylab.io.report import ReportResult

                    result, observations = value
                    self.config = result.config
                    self.hybrid_model = None
                    self.build()
                    summary = result.to_dict()
                    summary["observed_energy_wh"] = [o.energy_wh for o in observations]
                    summary["fitted_energy_wh"] = [
                        o.energy_wh + r
                        for o, r in zip(
                            observations,
                            result.residuals_wh / [o.weight**0.5 for o in observations],
                        )
                    ]
                    self.display_result(
                        ReportResult(
                            summary,
                            result.config,
                            {"observations": serialize_observations(observations)},
                        )
                    )

                self.submit(job, apply)
            except Exception as error:
                messagebox.showerror(self.s("error"), str(error))

    def learn(self, observations: Any) -> None:
        from bikeenergylab.residual import CGPRAModel

        if len(observations) < 40:
            raise ValueError(self.s("data_help"))
        cfg = self.read_config()

        def job() -> Any:
            import numpy as np

            seed = cfg.experiment.get("seed", 42)
            order = np.random.default_rng(seed).permutation(len(observations))
            model = CGPRAModel(cfg, seed=seed).fit([observations[i] for i in order[:-20]])
            model.calibrate_intervals([observations[i] for i in order[-20:]])
            held = model.interval_observations
            prediction = model.predict(held)
            return model, {
                "observed_energy_wh": [o.energy_wh for o in held],
                "fitted_energy_wh": prediction.energy_wh.tolist(),
                "diagnostic_alpha": prediction.alpha.tolist(),
                "diagnostic_ood_score": prediction.ood_score.tolist(),
                "diagnostic_scope": "independent interval calibration routes; not test metrics",
            }

        def apply(value: Any) -> None:
            from bikeenergylab.io.report import ReportResult

            model, diagnostics = value
            self.hybrid_model = model
            self.config = model.config
            self.build()
            self.display_result(
                ReportResult(
                    {
                        **diagnostics,
                        "CGPRA": "fitted",
                        "training_routes": len(model.training_groups),
                        "interval_routes": len(model.interval_groups),
                        "calibration": model.calibration_result.to_dict(),
                    },
                    model.config,
                    hybrid_model=model,
                )
            )

        self.submit(job, apply)

    def learn_csv(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Observations", "*.csv")])
        if path:
            from bikeenergylab.experiments.synthetic import observations_from_csv

            try:
                self.learn(observations_from_csv(path, self.read_config()))
            except Exception as error:
                messagebox.showerror(self.s("error"), str(error))

    def learn_demo(self) -> None:
        from bikeenergylab.experiments.synthetic import generate_observations

        try:
            self.learn(generate_observations(80, prefix="gui-synthetic"))
        except Exception as error:
            messagebox.showerror(self.s("error"), str(error))

    def load_model(self) -> None:
        path = filedialog.askdirectory()
        if path:
            from bikeenergylab.calibration import transfer_parameters
            from bikeenergylab.residual import CGPRAModel

            try:
                cfg = self.read_config()

                def apply(model: Any) -> None:
                    self.hybrid_model = model
                    self.config = transfer_parameters(cfg, model.config, model.parameter_names)
                    self.last_result = None
                    self.build()
                    self.display_result(
                        {
                            "CGPRA": "replayed and verified",
                            "model_directory": path,
                            "training_routes": len(model.training_groups),
                            "interval_routes": len(model.interval_groups),
                        }
                    )

                self.submit(lambda: CGPRAModel.load(path), apply)
            except Exception as error:
                messagebox.showerror(self.s("error"), str(error))

    def save_model(self) -> None:
        if self.hybrid_model is None:
            self.status.set(self.s("learn"))
            return
        directory = filedialog.askdirectory()
        if directory:
            destination = Path(directory) / f"CGPRA-{uuid.uuid4().hex[:12]}"
            model = self.hybrid_model
            self.submit(lambda: model.save(destination), lambda path: self.status.set(str(path)))

    def convert_telemetry(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Telemetry CSV", "*.csv")])
        if path:
            from bikeenergylab.experiments.synthetic import serialize_observations
            from bikeenergylab.io.report import ReportResult
            from bikeenergylab.io.telemetry import load_telemetry

            try:
                cfg = self.read_config()

                def job() -> Any:
                    observations, report = load_telemetry(path, cfg)
                    return ReportResult(
                        report, cfg, {"observations": serialize_observations(observations)}
                    )

                self.submit(job)
            except Exception as error:
                messagebox.showerror(self.s("error"), str(error))

    def update_model_csv(self, adapt: bool) -> None:
        if self.hybrid_model is None:
            self.status.set(self.s("learn"))
            return
        path = filedialog.askopenfilename(filetypes=[("Observations CSV", "*.csv")])
        if path:
            from bikeenergylab.experiments.synthetic import (
                observations_from_csv,
                serialize_observations,
            )
            from bikeenergylab.io.report import ReportResult

            model = deepcopy(self.hybrid_model)

            def job() -> Any:
                observations = observations_from_csv(path, model.config)
                updates = [model.adapt(o) for o in observations] if adapt else []
                if not adapt:
                    model.calibrate_intervals(observations)
                return ReportResult(
                    {
                        "updates": updates,
                        "training_routes": len(model.training_groups),
                        "interval_routes": len(model.interval_groups),
                        "intervals_available": bool(model.quantiles),
                    },
                    model.config,
                    {"supplied_observations": serialize_observations(observations)},
                    model,
                )

            def apply(result: Any) -> None:
                self.hybrid_model, self.config = result.hybrid_model, result.config
                self.build()
                self.display_result(result)

            self.submit(job, apply)

    def adapt_csv(self) -> None:
        self.update_model_csv(True)

    def interval_csv(self) -> None:
        self.update_model_csv(False)

    def run_sensitivity(self) -> None:
        from bikeenergylab.io.report import ReportResult
        from bikeenergylab.uncertainty.global_sensitivity import physical_sensitivity
        from bikeenergylab.uncertainty.sensitivity import one_at_a_time

        try:
            cfg, route, method = self.read_config(), self.route(), self.sensitivity_method.get()

            def job() -> Any:
                if method == "oat":
                    result = ReportResult(
                        {"method": "oat", "response": "full-route electrical demand [Wh]"},
                        cfg,
                        {"sensitivity": one_at_a_time(cfg, route), "route": route.frame},
                    )
                    return result, result.tables["sensitivity"]
                analysis = physical_sensitivity(
                    cfg,
                    route,
                    method,
                    n=16 if method == "morris" else 256,
                    seed=cfg.experiment.get("seed", 42),
                    **dict(cfg.experiment.get("sensitivity", {})),
                )
                return ReportResult(
                    analysis.protocol,
                    cfg,
                    {
                        "sensitivity": analysis.indices,
                        "evaluations": analysis.evaluations,
                        "route": route.frame,
                    },
                ), analysis.indices

            def apply(value: Any) -> None:
                result, indices = value
                result.summary["indices"] = indices.to_dict("records")
                self.display_result(result)

            self.submit(job, apply)
        except Exception as error:
            messagebox.showerror(self.s("error"), str(error))

    def run_suite(self) -> None:
        from bikeenergylab.experiments.suite import run_suite

        try:
            cfg = self.read_config()
            self.submit(
                lambda: run_suite(cfg),
                lambda path: self.display_result({"experiment_directory": str(path)}),
            )
        except Exception as error:
            messagebox.showerror(self.s("error"), str(error))

    def display_result(self, result: Any) -> None:
        self.last_result = result
        summary = dict(result.summary) if hasattr(result, "summary") else result
        self.result_text.delete("1.0", "end")
        self.result_text.insert("1.0", json.dumps(json_safe(summary), indent=2, ensure_ascii=False))
        for tab in self.plot_frame.tabs():
            if str(self.details_frame) != tab:
                self.plot_frame.forget(tab)
                self.root.nametowidget(tab).destroy()
        from .plots import result_figures

        for title, figure in result_figures(result, self.language.get()):
            frame = ttk.Frame(self.plot_frame)
            self.plot_frame.add(frame, text=title)
            self.draw_figure(figure, frame)
        if len(self.plot_frame.tabs()) > 1:
            self.plot_frame.select(1)
        self.navigation.selection_set("results")
        self.show("results")
        gc.collect()

    def export(self) -> None:
        if not hasattr(self.last_result, "export"):
            self.status.set(self.s("run"))
            return
        path = filedialog.askdirectory()
        if path:
            result = self.last_result
            self.submit(lambda: result.export(path), lambda output: self.status.set(str(output)))

    def close(self) -> None:
        self.closed = True
        self.callback = None
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()
        gc.collect()


def main(smoke_test: bool = False) -> int:
    root = tk.Tk()
    app = Application(root)
    if smoke_test:
        root.withdraw()
        errors = []
        original_error_dialog = messagebox.showerror
        original_unraisable_hook = sys.unraisablehook
        messagebox.showerror = lambda title, message: errors.append(str(message))

        def unraisable(error: Any) -> None:
            errors.append(str(error.exc_value))
            original_unraisable_hook(error)

        sys.unraisablehook = unraisable
        root.report_callback_exception = lambda kind, value, trace: errors.append(str(value))

        def finish_job() -> None:
            deadline = time.monotonic() + 45

            def check() -> None:
                if app.job is None or errors or time.monotonic() >= deadline:
                    root.quit()
                else:
                    root.after(20, check)

            # mainloop marks Tk's dispatcher active for supported cross-thread
            # cleanup. Repeated update() calls do not set that dispatcher state.
            root.after(20, check)
            root.mainloop()
            if app.job is not None or errors:
                raise RuntimeError(f"GUI job failed or timed out: {errors}")

        try:
            # Exercise actual selectors/actions and guide state across GUI rebuilds.
            app.example_selector.current(2)
            app.select_example()
            app.load_example()
            assert app.config.environment.wind_mps == -3
            assert app.current_route.distance_m == 3000
            app.start_tutorial()
            app.tutorial_action()
            assert app.config.environment.wind_mps == 0
            app.move_tutorial(1)
            app.tutorial_action()
            assert app.section == "rider"
            app.move_tutorial(1)
            app.tutorial_action()
            assert app.route_plot_frame.winfo_children()
            app.move_tutorial(1)
            app.tutorial_action()
            finish_job()
            assert app.last_result.summary["completed_route"]
            app.move_tutorial(1)
            app.tutorial_action()
            assert app.section == "results"
            app.language.set("en")
            app.change_language()
            assert app.tutorial_open and app.tutorial_index == 4
            assert app.example_key == "flat"
            assert "Flat route" in app.example_selector.get()
            app.move_tutorial(1)
            app.tutorial_action()
            finish_job()
            assert "mission_probability" in app.last_result.summary
            app.move_tutorial(1)
            original_directory_dialog = filedialog.askdirectory
            try:
                filedialog.askdirectory = lambda: str(Path("results/gui-smoke-onboarding"))
                app.tutorial_action()
                finish_job()
                assert (Path(app.status.get()) / "summary.json").is_file()
            finally:
                filedialog.askdirectory = original_directory_dialog
            app.move_tutorial(-1)
            assert app.tutorial_index == 5
            app.move_tutorial(1)
            app.move_tutorial(1)
            app.tutorial_action()
            assert not app.tutorial_open
            # The smaller fixture keeps existing hybrid workflow checks quick.
            app.current_route = None
            app.loaded_example_key = None
            app.config.route = {
                "kind": "synthetic",
                "distance_m": 100,
                "speed_mps": 7,
                "segments": 10,
            }
            app.run_simulation()
            finish_job()
            assert app.last_result.summary["completed_route"]
            assert len(app.plot_frame.tabs()) == 5
            app.show("battery")
            root.update_idletasks()
            assert app.section_canvases["battery"].cget("scrollregion")
            app.preview_route()
            app.language.set("en")
            app.change_language()
            root.update()
            assert app.navigation.item("route")["text"] == "Route"
            assert len(app.frames) == 15
            from bikeenergylab.experiments import generate_observations

            app.learn(generate_observations(40, 92, prefix="gui-smoke"))
            finish_job()
            assert app.hybrid_model is not None
            app.run_simulation()
            finish_job()
            assert "CGPRA" in app.last_result.summary
            cached_energy = app.last_result.summary["CGPRA"]["full_route_energy_wh"]
            app.language.set("es")
            app.change_language()
            assert app.last_result.summary["CGPRA"]["full_route_energy_wh"] == cached_energy
            app.config.uncertainty = {"n_samples": 4, "max_distance_km": 1}
            app.run_uncertainty()
            finish_job()
            assert "predictive_energy" in app.last_result.summary
            app.config.experiment["sensitivity"] = {"bounds": {"bike.crr": [0.004, 0.01]}}
            app.sensitivity_method.set("morris")
            app.run_sensitivity()
            finish_job()
            assert len(app.last_result.tables["evaluations"]) == 32
            if os.environ.get("BIKEENERGYLAB_GUI_ACCEPTANCE") == "1":
                from .acceptance import check_buttons

                check_buttons(
                    app,
                    Path(
                        os.environ.get(
                            "BIKEENERGYLAB_GUI_ACCEPTANCE_OUTPUT", "results/gui-button-verification"
                        )
                    ),
                )
        finally:
            messagebox.showerror = original_error_dialog
            app.close()
            sys.unraisablehook = original_unraisable_hook
        if errors:
            raise RuntimeError(f"GUI callback or cleanup errors: {errors}")
        print(
            "GUI smoke passed: examples selector, eight-step tutorial/export, physical/hybrid simulation, plots, scrollable forms, ES/EN, Tk cleanup"
        )
        return 0
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
