"""Exportable calibration, adaptation and conversion reports."""

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from bikeenergylab import Config


@dataclass
class ReportResult:
    summary: dict
    config: Config
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    hybrid_model: object | None = None

    def export(self, output: str | Path = "results", figures: bool = True) -> Path:
        from bikeenergylab.io import create_run, write_json

        destination = create_run(output, self.config, self.tables)
        write_json(destination / "summary.json", self.summary)
        if self.hybrid_model is not None:
            self.hybrid_model.save(destination / "model")
        if figures and ("observed_energy_wh" in self.summary or "sensitivity" in self.tables):
            from bikeenergylab.gui.plots import result_figures
            from bikeenergylab.visualization import save_figure

            for index, (_, figure) in enumerate(result_figures(self, "en")):
                save_figure(figure, destination / "figures" / f"diagnostics-{index}")
        return destination
