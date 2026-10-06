"""Packaged, offline learning examples and contextual ES/EN tutorial content."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bikeenergylab import BikeModel, Config, Route
from bikeenergylab.routes import route_from_config


@dataclass(frozen=True)
class Example:
    key: str
    titles: tuple[str, str]
    descriptions: tuple[str, str]
    operation: str = "simulation"

    def text(self, language: str, *, description: bool = False) -> str:
        return (self.descriptions if description else self.titles)[language == "en"]

    def configuration(self) -> Config:
        cfg = Config().changed("rider.human_power_w", 50)
        cfg.route = dict(kind="synthetic", distance_m=3000, speed_mps=6, grade=0, segments=30)
        cfg.experiment = {"name": f"guided_example_{self.key}", "seed": 42, "synthetic": True}
        if self.key == "hill":
            cfg.route.update(speed_mps=5, grade=0.03)
        elif self.key == "headwind":
            cfg.environment.wind_mps = -3
        elif self.key == "rider":
            cfg.rider.human_power_w = 120
        elif self.key == "cold":
            cfg.environment.temperature_c = 0
        elif self.key == "mission":
            cfg.battery.initial_soc = 0.38
            cfg.route.update(distance_m=26000, segments=100)
        if self.operation == "uncertainty":
            cfg.uncertainty = {
                "n_samples": 30,
                "seed": 48 if self.key == "mission" else 42,
                "max_distance_km": 80,
                "reserve_soc": 0.15 if self.key == "mission" else 0.1,
                "distributions": {
                    "environment.wind_mps": {"distribution": "normal", "mean": 0, "std": 1}
                },
            }
        cfg.validate()
        return cfg


EXAMPLES = (
    Example(
        "flat",
        ("01 · Ruta plana", "01 · Flat route"),
        (
            "Primer recorrido: 3 km a 6 m/s (21.6 km/h), sin pendiente y con 50 W humanos. Observe energía en Wh, consumo en Wh/km y SOC final. Es la referencia para comparar los ejemplos 02–05.",
            "First ride: 3 km at 6 m/s (21.6 km/h), level terrain and 50 W of rider power. Inspect energy in Wh, consumption in Wh/km and final SOC. Use this as the reference for examples 02–05.",
        ),
    ),
    Example(
        "hill",
        ("02 · Subida del 3%", "02 · 3% uphill"),
        (
            "Recorra 3 km a 5 m/s con pendiente 0.03 (3%). Compare la energía con la ruta plana y observe la contribución gravitacional en el balance. La velocidad también cambia en este ejemplo.",
            "Ride 3 km at 5 m/s on a 0.03 (3%) grade. Compare energy with the flat route and inspect the gravitational contribution to the balance. Speed also changes in this example.",
        ),
    ),
    Example(
        "headwind",
        ("03 · Viento frontal", "03 · Headwind"),
        (
            "La misma ruta plana con viento de −3 m/s. Compare el consumo con el ejemplo 01. Un viento negativo es frontal y aumenta la resistencia aerodinámica a esta velocidad.",
            "The same flat route with −3 m/s wind. Compare consumption with example 01. Negative wind is a headwind and increases aerodynamic resistance at this speed.",
        ),
    ),
    Example(
        "rider",
        ("04 · Mayor aporte humano", "04 · More rider power"),
        (
            "La misma ruta plana con 120 W en pedales. Compare con los 50 W del ejemplo 01: el motor necesita aportar menos energía. Revise las potencias humana, del motor y de batería.",
            "The same flat route with 120 W at the pedals. Compare with the 50 W in example 01: the motor supplies less energy. Inspect rider, motor and battery powers.",
        ),
    ),
    Example(
        "cold",
        ("05 · Ambiente frío", "05 · Cold weather"),
        (
            "La misma ruta a 0 °C. Observe el efecto de la densidad del aire. No se ha definido una curva térmica de batería: este ejemplo no supone una pérdida de capacidad por frío.",
            "The same route at 0 °C. Inspect the effect of air density. No battery temperature curve is defined: this example does not assume cold-induced capacity loss.",
        ),
    ),
    Example(
        "calibration",
        ("06 · Calibración sintética", "06 · Synthetic calibration"),
        (
            "Ajuste Crr y CdA con 40 rutas sintéticas sin ruido ni discrepancia. Los valores conocidos son Crr = 0.008 y CdA = 0.48 m². Revise el ajuste observado/predicho y los parámetros recuperados.",
            "Fit Crr and CdA using 40 synthetic routes without noise or discrepancy. Known values are Crr = 0.008 and CdA = 0.48 m². Inspect observed/predicted fit and recovered parameters.",
        ),
        "calibration",
    ),
    Example(
        "uncertainty",
        ("07 · Viento incierto y autonomía", "07 · Uncertain wind and range"),
        (
            "Ejecute 30 muestras con viento normal de media 0 y desviación 1 m/s. Revise dispersión de energía, bandas de SOC y autonomía. El horizonte de 80 km puede censurar la autonomía; revise ese indicador.",
            "Run 30 samples with normally distributed wind, mean 0 and standard deviation 1 m/s. Inspect energy spread, SOC bands and range. The 80 km horizon can censor range; check that indicator.",
        ),
        "uncertainty",
    ),
    Example(
        "hybrid",
        ("08 · Modelo híbrido CGPRA", "08 · CGPRA hybrid model"),
        (
            "Entrene con 60 rutas sintéticas y calibre intervalos con 25 rutas independientes; después simule la ruta plana. Revise energía CGPRA, alpha e indicador OOD. El modelo queda disponible para otras rutas y para guardar.",
            "Train on 60 synthetic routes and calibrate intervals on 25 independent routes, then simulate the flat route. Inspect CGPRA energy, alpha and OOD score. The model remains available for other routes and saving.",
        ),
        "hybrid",
    ),
    Example(
        "mission",
        ("09 · ¿Alcanza la batería?", "09 · Will the battery last?"),
        (
            "Ruta de 26 km, SOC inicial del 38%, reserva del 15% y viento incierto. Ejecute 30 muestras y revise mission_probability: exige completar la ruta con potencia suficiente y conservar la reserva.",
            "A 26 km route, 38% initial SOC, 15% reserve and uncertain wind. Run 30 samples and inspect mission_probability: it requires completing the route with sufficient power and retaining the reserve.",
        ),
        "uncertainty",
    ),
)


@dataclass
class ExampleRun:
    result: Any
    config: Config
    hybrid_model: Any = None


def execute_example(example: Example, cfg: Config, route: Route | None = None) -> ExampleRun:
    """Run the selected recipe using a GUI snapshot; never touch Tk in a worker."""
    route = route if route is not None else route_from_config(cfg)
    if example.operation == "uncertainty":
        from bikeenergylab.uncertainty import monte_carlo

        result = monte_carlo(cfg, route, **cfg.uncertainty)
    elif example.operation == "calibration":
        from bikeenergylab.calibration import calibrate
        from bikeenergylab.experiments import generate_observations
        from bikeenergylab.experiments.synthetic import serialize_observations
        from bikeenergylab.io.report import ReportResult

        data = generate_observations(
            40, seed=44, discrepancy=False, noise_std_wh_per_km=0, prefix="guided-calibration"
        )
        fit = calibrate(cfg, data)
        cfg = fit.config
        summary = fit.to_dict()
        summary.update(
            synthetic=True,
            known_crr=0.008,
            known_cda_m2=0.48,
            observed_energy_wh=[o.energy_wh for o in data],
            fitted_energy_wh=[
                o.energy_wh + r / o.weight**0.5 for o, r in zip(data, fit.residuals_wh)
            ],
        )
        result = ReportResult(summary, cfg, {"observations": serialize_observations(data)})
    elif example.operation == "hybrid":
        from bikeenergylab.experiments import generate_observations
        from bikeenergylab.residual import CGPRAModel

        model = CGPRAModel(cfg, seed=45).fit(
            generate_observations(60, seed=45, prefix="guided-training")
        )
        model.calibrate_intervals(generate_observations(25, seed=46, prefix="guided-interval"))
        cfg = model.config
        result = model.annotate_simulation(BikeModel(cfg).simulate(route))
        return ExampleRun(result, cfg, model)
    else:
        result = BikeModel(cfg).simulate(route)
    return ExampleRun(result, cfg)


@dataclass(frozen=True)
class TutorialStep:
    section: str
    action: str
    titles: tuple[str, str]
    descriptions: tuple[str, str]
    buttons: tuple[str, str]

    def text(self, field: str, language: str) -> str:
        return getattr(self, field)[language == "en"]


TUTORIAL = (
    TutorialStep(
        "home",
        "load",
        ("Su primera simulación", "Your first simulation"),
        (
            "Empezaremos con una ruta plana sintética de 3 km. Pulse Cargar ruta plana. Reemplazará la configuración en pantalla; los archivos guardados se conservan. Los ejemplos permiten practicar sin importar datos.",
            "Start with a synthetic 3 km flat route. Click Load flat route. This replaces the on-screen configuration; saved files are preserved. Examples let you practice without importing data.",
        ),
        ("Cargar ruta plana", "Load flat route"),
    ),
    TutorialStep(
        "bike",
        "rider",
        ("Entender los parámetros", "Understand the parameters"),
        (
            "Revise masa, Crr y CdA en Bicicleta. Pase el cursor sobre un campo para consultar su ayuda y unidades. En Ciclista, 50 W es potencia en pedales. Puede editar valores; Simular toma la configuración actual.",
            "Inspect mass, Crr and CdA in Bicycle. Hover over a field for help and units. In Rider, 50 W is pedal power. You can edit values; Simulate uses the current configuration.",
        ),
        ("Ver aporte del ciclista", "View rider power"),
    ),
    TutorialStep(
        "route",
        "preview",
        ("Comprobar la ruta", "Check the route"),
        (
            "Visualice elevación, velocidad, pendiente y superficie. 6 m/s equivale a 21.6 km/h; 0.03 significa pendiente del 3%. Si edita los campos de ruta, pulse Crear ruta manual para aplicarlos antes de simular.",
            "Preview elevation, speed, grade and surface. 6 m/s is 21.6 km/h; 0.03 means a 3% grade. If you edit route fields, click Create manual route to apply them before simulating.",
        ),
        ("Visualizar ruta", "Preview route"),
    ),
    TutorialStep(
        "simulation",
        "simulate",
        ("Ejecutar el cálculo", "Run the calculation"),
        (
            "Pulse Simular y espere a que termine. Durante el cálculo los controles se bloquean y la barra inferior indica Calculando. Al finalizar se abrirán los resultados automáticamente.",
            "Click Simulate and wait for completion. Controls are disabled while computing and the bottom bar shows Computing. Results open automatically when the calculation finishes.",
        ),
        ("Simular", "Simulate"),
    ),
    TutorialStep(
        "results",
        "results",
        ("Leer los resultados", "Read the results"),
        (
            "Explore las pestañas de potencias, batería y balance. Wh es energía; Wh/km es consumo por distancia; SOC es la fracción de carga. En Detalles, completed_route indica recorrido completo y feasible indica potencia suficiente. Revise ambos.",
            "Explore power, battery and balance tabs. Wh is energy; Wh/km is energy per distance; SOC is charge fraction. In Details, completed_route indicates completion and feasible indicates sufficient power. Check both.",
        ),
        ("Abrir gráficas", "Open plots"),
    ),
    TutorialStep(
        "uncertainty",
        "uncertainty",
        ("Practicar con incertidumbre", "Practice with uncertainty"),
        (
            "Esta acción carga y ejecuta el ejemplo 07: 30 muestras de viento incierto. Observe distribución de energía y bandas de SOC. Las probabilidades dependen de los supuestos; estas muestras sintéticas no verifican precisión real.",
            "This action loads and runs example 07: 30 uncertain-wind samples. Inspect the energy distribution and SOC bands. Probabilities depend on assumptions; these synthetic samples do not verify real-world accuracy.",
        ),
        ("Ejecutar ejemplo 07", "Run example 07"),
    ),
    TutorialStep(
        "export",
        "export",
        ("Guardar el trabajo", "Save your work"),
        (
            "Exporte el último resultado y elija una carpeta. Se crea una carpeta EXP nueva con configuración, tablas, metadatos y figuras. Guardar YAML en la barra superior conserva una configuración para abrirla después.",
            "Export the latest result and choose a folder. A new EXP folder contains configuration, tables, metadata and figures. Save YAML in the top bar preserves a configuration for reopening later.",
        ),
        ("Exportar resultado", "Export result"),
    ),
    TutorialStep(
        "home",
        "finish",
        ("Seguir explorando", "Keep exploring"),
        (
            "Ya conoce el flujo principal. Compare los ejemplos 01–05, pruebe la calibración 06, el híbrido 08 y la misión 09. Puede reiniciar este tutorial cuando quiera desde la barra superior; funciona sin conexión.",
            "You now know the main workflow. Compare examples 01–05, try calibration 06, hybrid 08 and mission 09. Restart this tutorial anytime from the top bar; it works offline.",
        ),
        ("Finalizar tutorial", "Finish tutorial"),
    ),
)
