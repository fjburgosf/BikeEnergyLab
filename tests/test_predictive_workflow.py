import json

import numpy as np
import pandas as pd
import pytest

from bikeenergylab import BikeModel, Config, Route
from bikeenergylab.calibration import Observation
from bikeenergylab.cli import main
from bikeenergylab.experiments import generate_observations
from bikeenergylab.experiments.synthetic import observations_from_csv, serialize_observations
from bikeenergylab.residual import CGPRAModel
from bikeenergylab.uncertainty import monte_carlo


@pytest.fixture(scope="module")
def calibrated_model():
    model = CGPRAModel(Config(), seed=17).fit(
        generate_observations(25, 17, prefix="predictive-train")
    )
    model.calibrate_intervals(generate_observations(25, 18, prefix="predictive-held"))
    return model


def test_observation_roundtrip_retains_profiles_weights_and_group(tmp_path):
    route = Route.synthetic(1000, 6, segments=5)
    route.frame["human_power_w"] = np.linspace(10, 80, 5)
    route.frame["wind_mps"] = np.linspace(-2, 2, 5)
    route.frame["temperature_c"] = np.linspace(5, 25, 5)
    original = Observation(route, 12, Config(), "001", 2.5)
    path = tmp_path / "observations.csv"
    serialize_observations([original]).to_csv(path, index=False)
    restored = observations_from_csv(str(path))[0]
    assert restored.group == "001"
    assert restored.weight == 2.5
    for column in ["human_power_w", "wind_mps", "temperature_c"]:
        np.testing.assert_array_equal(restored.route.frame[column], route.frame[column])
    assert BikeModel(restored.config).predict_energy(restored.route) == pytest.approx(
        BikeModel(original.config).predict_energy(route), abs=1e-12
    )
    with pytest.raises(ValueError, match="finite"):
        Observation(route, np.nan)


def test_model_replay_preserves_baselines_intervals_and_error_pool(calibrated_model, tmp_path):
    path = calibrated_model.save(tmp_path / "model")
    replay = CGPRAModel.load(path)
    query = generate_observations(3, 19, scenario="OOD-Route", prefix="replay-test")
    for baseline in ["M1", "M2", "M3", "M4"]:
        before = calibrated_model.predict(query, baseline, coverage=0.95)
        after = replay.predict(query, baseline, coverage=0.95)
        np.testing.assert_allclose(before.energy_wh, after.energy_wh, rtol=1e-8, atol=1e-8)
        np.testing.assert_allclose(before.lower_wh, after.lower_wh, rtol=1e-8, atol=1e-8)
        np.testing.assert_allclose(
            calibrated_model.signed_errors_wh_per_km[baseline],
            replay.signed_errors_wh_per_km[baseline],
            atol=1e-8,
        )
    with pytest.raises(FileExistsError):
        calibrated_model.save(path)
    with (path / "training.csv").open("a") as stream:
        stream.write("\n")
    with pytest.raises(ValueError, match="checksum"):
        CGPRAModel.load(path)


def test_failed_interval_recalibration_keeps_previous_valid_state(calibrated_model):
    quantiles = dict(calibrated_model.quantiles)
    groups = set(calibrated_model.interval_groups)
    with pytest.raises(ValueError, match="Too few"):
        calibrated_model.calibrate_intervals(generate_observations(4, 77, prefix="too-small"))
    assert calibrated_model.quantiles == quantiles
    assert calibrated_model.interval_groups == groups


def test_sampled_physics_override_is_not_overwritten_by_calibration(calibrated_model):
    query = generate_observations(2, 33, prefix="physical-override")
    physical = calibrated_model.physical(query)
    original = calibrated_model.predict(query)
    override = calibrated_model.predict(query, physical_energy_wh=physical + 7)
    np.testing.assert_allclose(override.energy_wh - original.energy_wh, 7)
    with pytest.raises(ValueError, match="one finite"):
        calibrated_model.predict(query, physical_energy_wh=np.array([1]))


def test_calibrated_latent_crr_does_not_create_artificial_ood(calibrated_model):
    original = calibrated_model.observations[:3]
    calibrated = [
        Observation(
            o.route,
            0,
            o.config.changed("bike.crr", calibrated_model.config.bike.crr),
            o.group,
        )
        for o in original
    ]
    for baseline in ["M1", "M2", "M3", "M4"]:
        before = calibrated_model.predict(original, baseline)
        after = calibrated_model.predict(calibrated, baseline)
        np.testing.assert_allclose(before.energy_wh, after.energy_wh, atol=1e-10)
        np.testing.assert_allclose(before.alpha, after.alpha, atol=1e-10)
        assert after.alpha.min() > 0.05


def test_physical_mc_draws_unchanged_and_full_demand_not_capped(calibrated_model):
    cfg = calibrated_model.config.changed("battery.initial_soc", 0.1001)
    route = Route.synthetic(1000, 6, segments=8)
    options = dict(
        n_samples=12,
        seed=81,
        max_distance_km=2,
        distributions={"bike.crr": {"distribution": "uniform", "low": 0.006, "high": 0.009}},
    )
    physical = monte_carlo(cfg, route, **options)
    learned = monte_carlo(cfg, route, hybrid_model=calibrated_model, **options)
    pd.testing.assert_frame_equal(physical.samples, learned.samples[physical.samples.columns])
    assert (learned.samples.full_route_demand_wh > learned.samples.energy_wh).all()
    assert learned.samples.predictive_energy_wh.std() > 0
    again = monte_carlo(cfg, route, hybrid_model=calibrated_model, **options)
    pd.testing.assert_frame_equal(learned.samples, again.samples)


def test_ood_gate_does_not_remove_predictive_error(calibrated_model):
    cfg = calibrated_model.config.changed("environment.wind_mps", -30)
    result = monte_carlo(
        cfg,
        Route.synthetic(500, 6, segments=5),
        n_samples=30,
        seed=82,
        max_distance_km=1,
        hybrid_model=calibrated_model,
    )
    assert np.max(result.samples.alpha) < 1e-10
    assert result.samples.predictive_error_wh_per_km.std() > 0
    assert result.summary["predictive_energy"]["outside_support_fraction"] == 1


def test_ecm_has_energy_predictions_but_no_aggregate_budget_probability(calibrated_model):
    cfg = calibrated_model.config.changed("battery.model", "ecm")
    result = monte_carlo(
        cfg,
        Route.synthetic(100, 6, segments=3),
        n_samples=3,
        max_distance_km=0.2,
        hybrid_model=calibrated_model,
    )
    assert result.samples.predictive_energy_wh.notna().all()
    assert result.samples.energy_budget_success.isna().all()
    predictive = result.summary["predictive_energy"]
    assert predictive["energy_budget_probability"] is None
    assert predictive["energy_budget_probability_bounds"] == [0, 1]


def test_unsupported_energy_draws_stay_visible_and_unidentified(calibrated_model, tmp_path):
    calibrated_model.save(tmp_path / "model")
    model = CGPRAModel.load(tmp_path / "model")
    model.signed_errors_wh_per_km["M4"] = np.full(25, -1000.0)
    result = monte_carlo(
        model.config,
        Route.synthetic(100, 6),
        n_samples=3,
        max_distance_km=1,
        hybrid_model=model,
    )
    assert (result.samples.predictive_energy_wh < 0).all()
    assert result.summary["predictive_energy"]["inadmissible_energy_fraction"] == 1
    assert result.summary["predictive_energy"]["energy_budget_probability_bounds"] == [0, 1]


def test_joint_profile_override_is_rejected():
    route = Route.synthetic(100, 6, wind_mps=1)
    joint = {
        "parameters": ["environment.wind_mps"],
        "mean": [0],
        "covariance": [[1]],
        "low": [-3],
        "high": [3],
    }
    with pytest.raises(ValueError, match="overridden"):
        monte_carlo(Config(), route, n_samples=2, joint_parameters=joint)


def test_adaptation_replay_and_stale_errors(calibrated_model, tmp_path):
    calibrated_model.save(tmp_path / "initial")
    model = CGPRAModel.load(tmp_path / "initial")
    model.adapt(generate_observations(1, 85, prefix="adapt-one")[0])
    assert not model.signed_errors_wh_per_km
    assert not model.quantiles
    with pytest.raises(ValueError, match="fresh"):
        monte_carlo(model.config, Route.synthetic(100, 6), n_samples=2, hybrid_model=model)
    with pytest.raises(ValueError, match="independent"):
        model.calibrate_intervals(calibrated_model.interval_observations)
    model.save(tmp_path / "adapted")
    restored = CGPRAModel.load(tmp_path / "adapted")
    next_observation = generate_observations(1, 86, prefix="adapt-two")[0]
    before, after = model.adapt(next_observation), restored.adapt(next_observation)
    assert before["innovation_wh"] == pytest.approx(after["innovation_wh"], abs=1e-8)
    np.testing.assert_allclose(model.sequential.covariance, restored.sequential.covariance)


def test_cli_prediction_simulation_export_and_portable_uncertainty(calibrated_model, tmp_path):
    model_path = calibrated_model.save(tmp_path / "model")
    cfg = Config.from_dict(calibrated_model.config.to_dict())
    cfg.route = {"kind": "synthetic", "distance_m": 100, "speed_mps": 6, "segments": 3}
    cfg.uncertainty = {"n_samples": 3, "max_distance_km": 1}
    import yaml

    configuration = tmp_path / "request.yaml"
    configuration.write_text(yaml.safe_dump(cfg.to_dict()), encoding="utf-8")
    output = tmp_path / "outputs"
    for command in ["predict", "simulate", "uncertainty"]:
        assert (
            main(
                [
                    command,
                    str(configuration),
                    "--model",
                    str(model_path),
                    "--output",
                    str(output),
                    "--no-figures",
                ]
            )
            == 0
        )
    runs = sorted(output.glob("EXP-*"))
    summaries = [json.loads((run / "summary.json").read_text(encoding="utf-8")) for run in runs]
    assert any("CGPRA" in summary for summary in summaries)
    predictive_run = next(
        run for run, summary in zip(runs, summaries) if "predictive_energy" in summary
    )
    assert (
        main(
            [
                "uncertainty",
                str(predictive_run / "config.yaml"),
                "--output",
                str(tmp_path / "rerun"),
                "--no-figures",
            ]
        )
        == 0
    )
    assert not list(predictive_run.glob("figures/*"))


def test_portable_motor_map_after_original_removed(tmp_path):
    from bikeenergylab.motor import generate_illustrative_map

    asset = tmp_path / "original_map.csv"
    generate_illustrative_map(asset)
    train = generate_observations(12, 41, prefix="map-training")
    for observation in train:
        observation.config = observation.config.changed("motor.efficiency_map", str(asset))
    cfg = Config().changed("motor.efficiency_map", str(asset))
    model = CGPRAModel(cfg, calibrate_physics=False).fit(train)
    model.save(tmp_path / "mapped-model")
    asset.unlink()
    replay = CGPRAModel.load(tmp_path / "mapped-model")
    query = replay.observations[:2]
    np.testing.assert_allclose(model.predict(query).energy_wh, replay.predict(query).energy_wh)


def test_cli_training_reproducible_group_split(tmp_path):
    data = tmp_path / "training.csv"
    serialize_observations(generate_observations(40, 90, prefix="cli-train")).to_csv(
        data, index=False
    )
    assert main(["train", str(data), "--output", str(tmp_path / "runs"), "--seed", "90"]) == 0
    run = next((tmp_path / "runs").glob("EXP-*"))
    report = json.loads((run / "training.json").read_text(encoding="utf-8"))
    assert len(report["training_groups"]) == 20
    assert len(report["held_out_groups"]) == 20
    assert not set(report["training_groups"]) & set(report["held_out_groups"])
    assert CGPRAModel.load(run / "model").seed == 90


def test_predictive_protocol_metrics_and_inputs(tmp_path):
    from bikeenergylab.experiments.predictive import run_predictive_validation

    run = run_predictive_validation(
        output=tmp_path, seeds=(8,), n_train=15, n_calibration=20, n_test=1, figures=False
    )
    metrics = pd.read_csv(run / "metrics.csv")
    assert len(metrics) == 8 * 4
    assert np.isfinite(metrics[["crps_wh", "energy_budget_brier"]]).all().all()
    assert metrics.empirical_coverage95.between(0, 1).all()
    budgets = pd.read_csv(run / "energy_budgets.csv")
    assert len(budgets) == 8 * 4 * 3
    assert budgets.probability.between(0, 1).all()
    assert (run / "seed-8" / "test-OOD-Temperature.csv").exists()
    assert CGPRAModel.load(run / "seed-8" / "model").interval_groups
    metadata = json.loads((run / "metadata.json").read_text(encoding="utf-8"))
    assert "seed-8/test-OOD-Temperature.csv" in metadata["input_sha256"]
    assert "seed-8/model/training.csv" in metadata["input_sha256"]


def test_export_replay_preserves_explicit_physical_configuration(calibrated_model, tmp_path):
    cfg = calibrated_model.config.changed("bike.crr", 0.003)
    result = monte_carlo(
        cfg,
        Route.synthetic(200, 6, segments=4),
        n_samples=3,
        seed=91,
        max_distance_km=1,
        hybrid_model=calibrated_model,
    )
    original = result.export(tmp_path / "original", figures=False)
    assert (
        main(
            [
                "uncertainty",
                str(original / "config.yaml"),
                "--output",
                str(tmp_path / "replayed"),
                "--no-figures",
            ]
        )
        == 0
    )
    replayed = next((tmp_path / "replayed").glob("EXP-*"))
    samples = pd.read_csv(replayed / "distributions.csv")
    np.testing.assert_allclose(
        samples.full_route_demand_wh, result.samples.full_route_demand_wh, atol=1e-10
    )
    np.testing.assert_allclose(
        samples.predictive_energy_wh, result.samples.predictive_energy_wh, atol=1e-8
    )
