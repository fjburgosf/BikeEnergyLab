from copy import deepcopy

import numpy as np
import pytest

from bikeenergylab import BikeModel
from bikeenergylab.gui.onboarding import EXAMPLES, TUTORIAL, execute_example
from bikeenergylab.routes import route_from_config


def example(key):
    return next(e for e in EXAMPLES if e.key == key)


def test_presets_are_independent_and_roundtrip_routes():
    for preset in EXAMPLES:
        cfg = preset.configuration()
        route = route_from_config(cfg)
        assert route.distance_m == cfg.route["distance_m"]
        assert cfg.experiment["synthetic"]
        cfg.route["distance_m"] = 1
        cfg.bike.surface_crr["asphalt"] = 0.1
        fresh = preset.configuration()
        assert fresh.route["distance_m"] >= 3000
        assert fresh.bike.surface_crr["asphalt"] == 0.006
    assert len({e.key for e in EXAMPLES}) == len(EXAMPLES)
    assert len({e.text("es") for e in EXAMPLES}) == len(EXAMPLES)
    assert len({e.text("en") for e in EXAMPLES}) == len(EXAMPLES)


def test_beginner_examples_have_physical_effects_and_complete():
    results = {}
    for preset in EXAMPLES[:5]:
        cfg = preset.configuration()
        outcome = execute_example(preset, cfg)
        assert outcome.result.summary["completed_route"]
        assert outcome.result.summary["feasible"]
        results[preset.key] = BikeModel(cfg).predict_energy(route_from_config(cfg))
    assert results["headwind"] > results["flat"] > results["rider"]
    assert results["hill"] > results["flat"]
    assert results["cold"] > results["flat"]


def test_calibration_example_recovers_truth_and_exports(tmp_path):
    preset = example("calibration")
    outcome = execute_example(preset, preset.configuration())
    assert outcome.hybrid_model is None
    assert outcome.config.bike.crr == pytest.approx(0.008, abs=1e-6)
    assert outcome.config.bike.cda_m2 == pytest.approx(0.48, abs=1e-6)
    assert len(outcome.result.tables["observations"].route_id.unique()) == 40
    output = outcome.result.export(tmp_path, figures=False)
    assert (output / "summary.json").is_file()
    assert (output / "observations.csv").is_file()


def test_hybrid_example_keeps_reusable_model_and_independent_intervals():
    preset = example("hybrid")
    outcome = execute_example(preset, preset.configuration())
    model = outcome.hybrid_model
    assert len(model.training_groups) == 60
    assert len(model.interval_groups) == 25
    assert not set(model.training_groups) & set(model.interval_groups)
    assert "CGPRA" in outcome.result.summary
    assert np.isfinite(outcome.result.summary["CGPRA"]["full_route_energy_wh"])


@pytest.mark.parametrize("key", ["uncertainty", "mission"])
def test_uncertainty_examples_use_their_mission_settings(key):
    preset = example(key)
    cfg = preset.configuration()
    before = deepcopy(cfg.to_dict())
    # Small deterministic integration sample; the full 30-sample recipe is checked in GUI smoke.
    cfg.uncertainty["n_samples"] = 3
    cfg.uncertainty["max_distance_km"] = 1
    outcome = execute_example(preset, cfg)
    assert 0 <= outcome.result.summary["mission_probability"] <= 1
    assert cfg.battery.initial_soc == before["battery"]["initial_soc"]
    assert cfg.uncertainty["reserve_soc"] == (0.15 if key == "mission" else 0.1)
    assert cfg.route["distance_m"] == (26000 if key == "mission" else 3000)


def test_tutorial_covers_complete_workflow_in_both_languages():
    from bikeenergylab.gui.app import Application
    from bikeenergylab.gui.strings import STRINGS

    assert set(STRINGS["es"]) == set(STRINGS["en"])
    assert {"load", "preview", "simulate", "results", "uncertainty", "export", "finish"} <= {
        step.action for step in TUTORIAL
    }
    for step in TUTORIAL:
        assert step.section in Application.sections
        for lang in ("es", "en"):
            assert step.text("titles", lang)
            assert step.text("descriptions", lang)
            assert step.text("buttons", lang)
