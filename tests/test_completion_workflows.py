from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from bikeenergylab import BikeModel, Config, Route
from bikeenergylab.cli import main
from bikeenergylab.experiments import generate_observations
from bikeenergylab.experiments.adaptive import prequential_evaluate
from bikeenergylab.experiments.synthetic import serialize_observations
from bikeenergylab.gui.plots import result_figures, route_figure
from bikeenergylab.residual import CGPRAModel
from bikeenergylab.uncertainty import monte_carlo
from bikeenergylab.uncertainty.global_sensitivity import analyze_global, physical_sensitivity


def test_morris_linear_signed_effects_and_design():
    result = analyze_global(
        lambda x: 2 * x[0] - 3 * x[1], {"x": [0, 1], "y": [0, 1]}, "morris", n=16, seed=7
    )
    np.testing.assert_allclose(result.indices.mu, [2, -3], atol=1e-12)
    np.testing.assert_allclose(result.indices.mu_star, [2, 3], atol=1e-12)
    np.testing.assert_allclose(result.indices.sigma, 0, atol=1e-12)
    assert len(result.evaluations) == 16 * 3
    assert result.evaluations[["x", "y"]].min().min() >= 0
    assert result.evaluations[["x", "y"]].max().max() <= 1 + 1e-12


def test_sobol_ishigami_reference_and_interactions():
    result = analyze_global(
        lambda x: np.sin(x[0]) + 7 * np.sin(x[1]) ** 2 + 0.1 * x[2] ** 4 * np.sin(x[0]),
        {key: [-np.pi, np.pi] for key in ["x", "y", "z"]},
        "sobol",
        n=4096,
        seed=11,
        bootstrap=40,
    )
    np.testing.assert_allclose(result.indices.S1, [0.313905, 0.442411, 0], atol=0.025)
    np.testing.assert_allclose(result.indices.ST, [0.557588, 0.442411, 0.243683], atol=0.025)
    assert (result.indices.ST_high95 >= result.indices.ST_low95).all()
    assert len(result.evaluations) == 4096 * 5


def test_global_sensitivity_constant_and_invalid_design():
    constant = analyze_global(lambda x: 4, {"x": [0, 1]}, n=16, bootstrap=4)
    assert constant.indices.S1.isna().all()
    assert not constant.protocol["variance_defined"]
    with pytest.raises(ValueError, match="power of two"):
        analyze_global(lambda x: x[0], {"x": [0, 1]}, n=19)
    with pytest.raises(ValueError, match="upper bound"):
        analyze_global(lambda x: 0, {"x": [1, 0]})
    with pytest.raises(ValueError, match="even integer"):
        analyze_global(lambda x: x[0], {"x": [0, 1]}, "morris", levels=5)


def test_sensitivity_reproducibility_and_profile_override():
    route = Route.synthetic(100, 5, segments=4)
    bounds = {"bike.crr": [0.005, 0.008], "route.speed_mps": [4, 6]}
    a = physical_sensitivity(Config(), route, "spearman", bounds, n=32, seed=18)
    b = physical_sensitivity(Config(), route, "spearman", bounds, n=32, seed=18)
    pd.testing.assert_frame_equal(a.evaluations, b.evaluations)
    assert a.indices.spearman_rho.notna().all()
    route.frame["wind_mps"] = 1
    with pytest.raises(ValueError, match="overridden"):
        physical_sensitivity(Config(), route, bounds={"environment.wind_mps": [-2, 2]}, n=8)


def test_gpx_timestamped_stationary_intervals(tmp_path):
    path = tmp_path / "stops.gpx"
    path.write_text(
        """<gpx><trk><trkseg>
      <trkpt lat="4" lon="-74"><ele>100</ele><time>2026-01-01T00:00:00Z</time></trkpt>
      <trkpt lat="4" lon="-74"><ele>100</ele><time>2026-01-01T00:00:10Z</time></trkpt>
      <trkpt lat="4.001" lon="-74"><ele>100</ele><time>2026-01-01T00:00:30Z</time></trkpt>
      </trkseg></trk></gpx>""",
        encoding="utf-8",
    )
    route = Route.from_gpx(path, smoothing_window=1)
    assert route.frame.dt_s.tolist() == [10, 20]
    assert route.frame.speed_mps.iloc[0] == 0
    assert route.distance_m > 100
    cfg = Config().changed("rider.human_power_w", 0)
    profile = BikeModel(cfg).operating_profile(route)
    assert profile.power_battery_requested_w.iloc[0] == cfg.simulation.auxiliary_power_w


def test_uncertainty_bands_do_not_extrapolate_depleted_routes(tmp_path):
    cfg = Config().changed("battery.nominal_energy_wh", 5).changed("rider.human_power_w", 0)
    result = monte_carlo(cfg, Route.synthetic(2000, 6, segments=10), n_samples=4, max_distance_km=3)
    bands = result.trajectory_bands
    assert bands.n_reached.iloc[0] == 4
    assert bands.n_reached.iloc[-1] == 0
    assert np.isnan(bands.soc_median.iloc[-1])
    destination = result.export(tmp_path, figures=False)
    assert (destination / "trajectory_bands.csv").is_file()


def test_telemetry_timestamps_use_seconds_across_datetime_resolutions(tmp_path):
    from bikeenergylab.io.telemetry import load_telemetry

    path = tmp_path / "timed.csv"
    pd.DataFrame(
        {
            "timestamp": ["2026-01-01T00:00:00Z", "2026-01-01T00:00:10Z"],
            "distance_m": [0, 30],
            "voltage_v": [36, 36],
            "current_a": [2, 2],
        }
    ).to_csv(path, index=False)
    observations, _ = load_telemetry(path)
    assert observations[0].energy_wh == pytest.approx(0.2)
    assert observations[0].route.frame.dt_s.iloc[0] == 10
    assert observations[0].route.frame.speed_mps.iloc[0] == 3


@pytest.fixture(scope="module")
def fitted_model():
    return CGPRAModel(seed=61).fit(generate_observations(12, 61, prefix="completion-fit"))


def test_fit_failure_is_atomic(fitted_model, monkeypatch):
    previous = fitted_model.config.bike.crr
    groups = set(fitted_model.training_groups)

    def fail(staged, observations):
        staged.config = staged.config.changed("bike.crr", 0.02)
        staged.training_groups.clear()
        raise RuntimeError("failed statistical stage")

    monkeypatch.setattr(CGPRAModel, "_fit_in_place", fail)
    with pytest.raises(RuntimeError):
        fitted_model.fit(generate_observations(10, 60))
    assert fitted_model.config.bike.crr == previous
    assert fitted_model.training_groups == groups


def test_adaptation_failure_is_atomic(fitted_model, monkeypatch):
    previous = fitted_model.config.bike.crr
    groups = set(fitted_model.training_groups)

    def fail(staged, observations):
        raise RuntimeError("failed residual rebuild")

    monkeypatch.setattr(CGPRAModel, "_fit_in_place", fail)
    with pytest.raises(RuntimeError):
        fitted_model.adapt(generate_observations(1, 62, prefix="failed-update")[0])
    assert fitted_model.config.bike.crr == previous
    assert fitted_model.training_groups == groups
    assert not hasattr(fitted_model, "sequential")


def test_prequential_predictions_precede_target_ingestion(fitted_model):
    stream = generate_observations(3, 63, prefix="causal-stream")
    changed = deepcopy(stream)
    changed[-1].energy_wh += 8
    first, first_model = prequential_evaluate(fitted_model, stream)
    second, second_model = prequential_evaluate(fitted_model, changed)
    np.testing.assert_array_equal(first.predicted_wh, second.predicted_wh)
    assert first_model.config.bike.crr != second_model.config.bike.crr
    assert len(fitted_model.training_groups) == 12
    result = first_model.annotate_simulation(
        BikeModel(first_model.config).simulate(stream[0].route)
    )
    assert result.summary["CGPRA"]["prediction_interval_wh"] is None


def test_offline_refit_resets_old_sequential_state(fitted_model):
    model = deepcopy(fitted_model)
    model.adapt(generate_observations(1, 67, prefix="old-sequential")[0])
    assert model.sequential.updates == 1
    model.fit(generate_observations(12, 68, prefix="fresh-offline"))
    assert not hasattr(model, "sequential")
    model.adapt(generate_observations(1, 69, prefix="fresh-update")[0])
    assert model.sequential.updates == 1


def test_cli_telemetry_and_sensitivity_exports(tmp_path):
    assert (
        main(
            ["telemetry", "datasets/telemetry_example.csv", "--output", str(tmp_path / "telemetry")]
        )
        == 0
    )
    exported = next((tmp_path / "telemetry").glob("EXP-*/observations.csv"))
    assert "observed_route_energy_wh" in pd.read_csv(exported)
    assert (
        main(
            [
                "sensitivity",
                "configs/flat.yaml",
                "--method",
                "morris",
                "--samples",
                "4",
                "--output",
                str(tmp_path / "morris"),
                "--no-figures",
            ]
        )
        == 0
    )
    assert next((tmp_path / "morris").glob("EXP-*/sensitivity.csv")).is_file()


def test_cli_adaptation_saved_model_and_point_prediction(fitted_model, tmp_path):
    model_path = fitted_model.save(tmp_path / "initial")
    stream_path = tmp_path / "new.csv"
    serialize_observations(generate_observations(1, 64, prefix="cli-new")).to_csv(
        stream_path, index=False
    )
    output = tmp_path / "adapted"
    assert main(["adapt", str(model_path), str(stream_path), "--output", str(output)]) == 0
    adapted_path = next(output.glob("EXP-*/model"))
    assert (
        main(
            [
                "predict",
                "configs/flat.yaml",
                "--model",
                str(adapted_path),
                "--point-only",
                "--output",
                str(tmp_path / "points"),
                "--no-figures",
            ]
        )
        == 0
    )
    replay = CGPRAModel.load(adapted_path)
    assert replay.sequential.updates == 1
    assert not replay.quantiles


def test_complete_translated_figures_render(tmp_path):
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    route = Route.synthetic(100, 5, segments=5)
    result = BikeModel(Config()).simulate(route)
    for language in ["es", "en"]:
        panels = result_figures(result, language)
        assert len(panels) == 4
        for index, (_, figure) in enumerate(panels):
            FigureCanvasAgg(figure).draw()
            figure.savefig(tmp_path / f"{language}-{index}.png")
        assert len(route_figure(route, language).axes) == 4
