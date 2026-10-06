"""Opt-in GUI acceptance: invoke actual widgets with controlled dialog responses."""

from __future__ import annotations

import hashlib
import json
import time
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from unittest.mock import patch

import yaml

from bikeenergylab import Config, Route, __version__
from bikeenergylab.experiments.synthetic import generate_observations, serialize_observations

from .onboarding import EXAMPLES, TUTORIAL


def widgets(parent):
    for child in parent.winfo_children():
        yield child
        yield from widgets(child)


def check_buttons(app, output: Path) -> None:
    """Exercise callbacks under Tk mainloop, including file and scientific actions.

    File chooser responses are injected. This verifies button wiring and the chosen
    files, not native Windows dialog rendering or every possible input/state.
    """
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    fixtures = output / "fixtures"
    fixtures.mkdir(exist_ok=True)
    cases, handled_errors, responses = [], [], []
    example_energy = {}
    report_path = output / "verification.json"

    def report(success):
        report_path.write_text(
            json.dumps(
                {
                    "version": __version__,
                    "completed_utc": datetime.now(timezone.utc).isoformat(),
                    "passed": success,
                    "cases_passed": sum(c["passed"] for c in cases),
                    "cases": cases,
                    "example_energy_wh": example_energy,
                    "dialog_responses": "injected for deterministic file actions",
                    "limits": [
                        "Native Windows dialogs and every possible screen/input state are not certified",
                        "Synthetic fixtures do not establish field accuracy",
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def dialog(**kwargs):
        if not responses:
            raise AssertionError("Unexpected file dialog")
        return str(responses.pop(0))

    def wait_job():
        if app.job is None:
            return
        deadline = time.monotonic() + 300

        def poll():
            if app.job is None or handled_errors or time.monotonic() >= deadline:
                app.root.quit()
            else:
                app.root.after(25, poll)

        app.root.after(25, poll)
        app.root.mainloop()
        assert app.job is None, "GUI worker did not finish"
        assert not handled_errors, handled_errors

    def invoke_text(text, parent=None):
        found = [
            w
            for w in widgets(parent or app.root)
            if isinstance(w, (ttk.Button, tk.Button, ttk.Checkbutton, tk.Checkbutton))
            and str(w.cget("text")) == text
        ]
        assert len(found) == 1, (text, len(found))
        assert str(found[0].cget("state")) != "disabled", text
        found[0].invoke()

    def invoke(key, parent=None):
        invoke_text(app.s(key), parent)

    def case(name, action, verify=lambda: None, *, expected_error=False):
        handled_errors.clear()
        try:
            action()
            if not expected_error:
                wait_job()
                assert not handled_errors, handled_errors
            else:
                assert handled_errors, "Invalid input must present an error"
            verify()
            assert not responses, "Unused file-dialog response"
            cases.append({"case": name, "passed": True})
            print(f"GUI button passed: {name}", flush=True)
        except BaseException as error:
            cases.append({"case": name, "passed": False, "error": str(error)})
            report(False)
            raise

    def choose(key, path, parent=None):
        responses.append(path)
        invoke(key, parent)

    def assert_true(value, message):
        assert value, message

    def reset_short_route():
        app.config = Config()
        app.config.route = {"kind": "synthetic", "distance_m": 100, "speed_mps": 6, "segments": 4}
        app.config.simulation.timestep_s = 30
        app.current_route = None
        app.hybrid_model = app.last_result = None
        app.loaded_example_key = None
        app.build()

    cfg = Config()
    cfg.route = {"kind": "synthetic", "distance_m": 100, "speed_mps": 6, "segments": 4}
    cfg.simulation.timestep_s = 30
    config_path = fixtures / "valid.yaml"
    config_path.write_text(yaml.safe_dump(cfg.to_dict()), encoding="utf-8")
    saved_config = fixtures / "saved.yaml"
    invalid_config = fixtures / "invalid.yaml"
    invalid_config.write_text("bike: [unterminated", encoding="utf-8")
    route_path = fixtures / "route.csv"
    Route.synthetic(120, 5, segments=4).frame.to_csv(route_path, index=False)
    gpx_path = fixtures / "route.gpx"
    gpx_path.write_text(
        '<gpx><trk><trkseg><trkpt lat="4" lon="-74"><ele>100</ele></trkpt>'
        '<trkpt lat="4.001" lon="-74"><ele>102</ele></trkpt></trkseg></trk></gpx>',
        encoding="utf-8",
    )
    train_path = fixtures / "training.csv"
    serialize_observations(generate_observations(40, 8821, prefix="button-training")).to_csv(
        train_path, index=False
    )
    fit_path = fixtures / "calibration.csv"
    serialize_observations(
        generate_observations(
            40, 8822, discrepancy=False, noise_std_wh_per_km=0, prefix="button-fit"
        )
    ).to_csv(fit_path, index=False)
    adapt_path = fixtures / "adapt.csv"
    serialize_observations(generate_observations(1, 8823, prefix="button-adapt")).to_csv(
        adapt_path, index=False
    )
    interval_path = fixtures / "intervals.csv"
    serialize_observations(generate_observations(20, 8824, prefix="button-intervals")).to_csv(
        interval_path, index=False
    )
    telemetry_path = fixtures / "telemetry.csv"
    telemetry_path.write_text(
        "timestamp,distance_m,voltage_v,current_a\n2026-10-06T00:00:00Z,0,36,2\n2026-10-06T00:00:10Z,30,36,2\n",
        encoding="utf-8",
    )

    with (
        patch.object(filedialog, "askopenfilename", dialog),
        patch.object(filedialog, "asksaveasfilename", dialog),
        patch.object(filedialog, "askdirectory", dialog),
        patch.object(
            messagebox, "showerror", lambda title, message: handled_errors.append(str(message))
        ),
    ):
        try:
            reset_short_route()
            for language in ["es", "en"]:
                selector = next(
                    w
                    for w in widgets(app.root)
                    if isinstance(w, ttk.Combobox) and tuple(w.cget("values")) == ("es", "en")
                )
                selector.set(language)
                selector.event_generate("<<ComboboxSelected>>")
                app.root.update()
                assert app.language.get() == language
                for section in app.sections:

                    def navigate(section=section):
                        app.navigation.selection_set(section)
                        app.navigation.event_generate("<<TreeviewSelect>>")
                        app.root.update_idletasks()

                    case(
                        f"navigation_{language}_{section}",
                        navigate,
                        lambda section=section: assert_true(app.section == section, section),
                    )
            case(
                "open_yaml",
                lambda: choose("load", config_path),
                lambda: assert_true(app.config.route["distance_m"] == 100, "YAML route"),
            )
            case(
                "save_yaml",
                lambda: choose("save", saved_config),
                lambda: assert_true(
                    Config.from_yaml(saved_config).route["distance_m"] == 100, "Saved YAML"
                ),
            )
            for key in [
                "load",
                "save",
                "csv",
                "gpx",
                "calibrate",
                "learn",
                "telemetry",
                "load_model",
            ]:
                case(f"cancel_{key}", lambda key=key: choose(key, ""))
            original_config = app.config.to_dict()
            case(
                "invalid_yaml_file",
                lambda: choose("load", invalid_config),
                lambda: assert_true(
                    app.config.to_dict() == original_config, "Invalid YAML changed config"
                ),
                expected_error=True,
            )
            case(
                "import_route_csv",
                lambda: choose("csv", route_path),
                lambda: assert_true(app.current_route.distance_m == 120, "CSV distance"),
            )
            case(
                "import_route_gpx",
                lambda: choose("gpx", gpx_path),
                lambda: assert_true(110 < app.current_route.distance_m < 112, "GPX distance"),
            )
            app.route_values["distance_m"].set("100")
            app.route_values["speed_mps"].set("6")
            app.route_values["grade"].set("0.01")
            case(
                "create_manual_route",
                lambda: invoke("manual"),
                lambda: assert_true(app.current_route.distance_m == 100, "Manual route"),
            )
            case(
                "preview_route",
                lambda: invoke("preview", app.frames["route"]),
                lambda: assert_true(
                    bool(app.route_plot_frame.winfo_children()), "Preview figure missing"
                ),
            )
            case(
                "simulate",
                lambda: invoke("run"),
                lambda: assert_true(app.last_result.summary["completed_route"], "Route incomplete"),
            )
            figure_tab = app.root.nametowidget(app.plot_frame.tabs()[1])
            for label in ["Home", "Pan", "Pan", "Zoom", "Zoom"]:
                case(
                    f"plot_toolbar_{label}_{len(cases)}",
                    lambda label=label: invoke_text(label, figure_tab),
                )
            for extension in ["png", "svg", "pdf"]:
                destination = fixtures / f"toolbar-figure.{extension}"

                def save_figure(destination=destination):
                    responses.append(destination)
                    invoke_text("Save", figure_tab)

                case(
                    f"plot_toolbar_save_{extension}",
                    save_figure,
                    lambda destination=destination: assert_true(
                        destination.is_file() and destination.stat().st_size > 100, "Figure missing"
                    ),
                )
            case(
                "export_result",
                lambda: choose("export_result", output / "exports"),
                lambda: assert_true(
                    (Path(app.status.get()) / "summary.json").is_file(), "Export missing"
                ),
            )
            for key in ["export_result"]:
                case(f"cancel_{key}", lambda key=key: choose(key, ""))
            app.yaml_editor.delete("1.0", "end")
            app.yaml_editor.insert("1.0", yaml.safe_dump(cfg.to_dict()))
            case(
                "apply_yaml",
                lambda: invoke("apply"),
                lambda: assert_true(app.config.route["distance_m"] == 100, "Applied YAML"),
            )
            app.yaml_editor.delete("1.0", "end")
            app.yaml_editor.insert("1.0", "simulation: [unterminated")
            case("invalid_yaml_editor", lambda: invoke("apply"), expected_error=True)
            app.refresh_yaml()
            case(
                "calibrate_csv",
                lambda: choose("calibrate", fit_path),
                lambda: assert_true(
                    abs(app.config.bike.crr - 0.008) < 1e-5, "Known Crr not recovered"
                ),
            )
            case(
                "convert_telemetry",
                lambda: choose("telemetry", telemetry_path),
                lambda: assert_true(
                    abs(
                        app.last_result.tables["observations"].observed_route_energy_wh.iloc[0]
                        - 0.2
                    )
                    < 1e-10,
                    "Telemetry energy",
                ),
            )
            case(
                "train_model_csv",
                lambda: choose("learn", train_path),
                lambda: assert_true(
                    app.hybrid_model is not None and bool(app.hybrid_model.quantiles),
                    "Trained model missing",
                ),
            )
            case(
                "save_model",
                lambda: choose("save_model", fixtures / "models"),
                lambda: assert_true(
                    (Path(app.status.get()) / "manifest.json").is_file(), "Saved model missing"
                ),
            )
            saved_model = Path(app.status.get())
            model_hash = hashlib.sha256((saved_model / "manifest.json").read_bytes()).hexdigest()
            case(
                "open_model",
                lambda: choose("load_model", saved_model),
                lambda: assert_true(
                    app.last_result["CGPRA"] == "replayed and verified", "Replay missing"
                ),
            )
            case(
                "adapt_model_csv",
                lambda: choose("adapt", adapt_path),
                lambda: assert_true(
                    not app.hybrid_model.quantiles, "Adaptation did not invalidate intervals"
                ),
            )
            case(
                "fresh_interval_calibration",
                lambda: choose("intervals", interval_path),
                lambda: assert_true(bool(app.hybrid_model.quantiles), "Fresh intervals missing"),
            )
            assert (
                hashlib.sha256((saved_model / "manifest.json").read_bytes()).hexdigest()
                == model_hash
            )
            for key in ["save_model", "adapt", "intervals"]:
                case(f"cancel_{key}", lambda key=key: choose(key, ""))
            app.config.uncertainty = {"n_samples": 4, "max_distance_km": 1}
            app.current_route = Route.synthetic(100, 6, segments=4)
            app.build()
            case(
                "mission_probability",
                lambda: invoke("probability"),
                lambda: assert_true(
                    "predictive_energy" in app.last_result.summary, "Predictive MC missing"
                ),
            )
            case(
                "train_synthetic_demo",
                lambda: invoke("demo"),
                lambda: assert_true(
                    app.last_result.summary["training_routes"] == 60, "Demo training split"
                ),
            )
            reset_short_route()
            app.config.experiment["sensitivity"] = {"bounds": {"bike.crr": [0.004, 0.01]}}
            for method in ["oat", "spearman", "morris", "sobol"]:
                app.sensitivity_method.set(method)
                case(
                    f"sensitivity_{method}",
                    lambda: invoke("sensitivity"),
                    lambda: assert_true(bool(app.last_result.tables), "Sensitivity tables missing"),
                )
            app.config.experiment.update(n_train=20, n_calibration=20, n_test=2)
            case(
                "id_ood_benchmark",
                lambda: invoke("benchmark"),
                lambda: assert_true(
                    (Path(app.last_result["benchmark_directory"]) / "metrics.csv").is_file(),
                    "Benchmark metrics missing",
                ),
            )
            case(
                "exp_01_to_15",
                lambda: invoke("suite"),
                lambda: assert_true(
                    (
                        Path(app.last_result["experiment_directory"]) / "experiment_index.json"
                    ).is_file(),
                    "Experiment index missing",
                ),
            )
            case(
                "show_examples",
                lambda: invoke("examples"),
                lambda: assert_true(app.section == "home", "Examples navigation"),
            )
            for index, example in enumerate(EXAMPLES):
                app.example_selector.current(index)
                app.example_selector.event_generate("<<ComboboxSelected>>")
                app.root.update()
                case(
                    f"load_example_{example.key}",
                    lambda: invoke("load_example"),
                    lambda example=example: assert_true(
                        app.example_key == example.key, "Example selection"
                    ),
                )
                case(
                    f"simulate_loaded_example_{example.key}",
                    lambda: invoke("run"),
                    lambda example=example: assert_true(
                        app.last_result is not None
                        and (
                            ("mission_probability" in app.last_result.summary)
                            if example.operation == "uncertainty"
                            else ("known_crr" in app.last_result.summary)
                            if example.operation == "calibration"
                            else ("CGPRA" in app.last_result.summary)
                            if example.operation == "hybrid"
                            else bool(app.last_result.summary["completed_route"])
                        ),
                        "Simulate did not execute the loaded example workflow",
                    ),
                )
                if example.operation == "simulation":
                    example_energy[example.key] = float(app.last_result.summary["energy_wh"])

            case(
                "tutorial_toolbar",
                lambda: invoke("tutorial"),
                lambda: assert_true(app.tutorial_open, "Guide missing"),
            )
            case(
                "loaded_example_energy_comparisons",
                lambda: None,
                lambda: assert_true(
                    example_energy["headwind"] > example_energy["flat"]
                    and example_energy["hill"] > example_energy["flat"]
                    and example_energy["rider"] < example_energy["flat"],
                    "Simulate reused another example instead of the loaded parameters",
                ),
            )
            case(
                "close_tutorial",
                lambda: invoke("close_tutorial", app.tutorial_frame),
                lambda: assert_true(not app.tutorial_open, "Guide did not close"),
            )
            case(
                "start_tutorial_home",
                lambda: invoke("start_tutorial", app.frames["home"]),
                lambda: assert_true(app.tutorial_index == 0, "Guide start"),
            )
            for index, step in enumerate(TUTORIAL):
                if step.action == "export":
                    responses.append(output / "tutorial-export")
                case(
                    f"tutorial_action_{index + 1}",
                    lambda step=step: invoke_text(
                        step.text("buttons", app.language.get()), app.tutorial_frame
                    ),
                )
                if index < len(TUTORIAL) - 1:
                    case(f"tutorial_next_{index + 1}", lambda: invoke("next", app.tutorial_frame))
            assert not app.tutorial_open
            report(True)
        except BaseException:
            report(False)
            raise
    print(f"GUI button acceptance passed: {len(cases)} checks; report {report_path}", flush=True)
