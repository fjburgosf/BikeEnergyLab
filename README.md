# BikeEnergyLab

**BikeEnergyLab: A Scientific Framework for Energy Consumption and Range Modeling of Electric Bicycles**

BikeEnergyLab es un framework científico para modelado, calibración, predicción e
investigación reproducible del consumo energético y autonomía de bicicletas eléctricas.
Versión **1.0.0**. La carpeta de partida estaba vacía. Véase el
[diagnóstico](docs/diagnostic.md). No se dispone de validación con bicicletas reales.

## Capacidades

- Dinámica longitudinal SI: rodadura, pendiente, viento con signo, aceleración.
- Ciclista constante, perfiles temporales o respuesta configurable a pendiente,
  cadencia y fatiga. Asistencia genérica por demanda o proporcional.
- Motor con eficiencia constante o mapa CSV, torque, potencia, velocidad y corriente limitados.
- Batería energética/SOC y Thevenin de un RC con conteo de coulombs. SOC mínimo/máximo.
- Temperatura por densidad del aire y curvas empíricas opcionales. Regeneración opt-in.
- Rutas manuales, sintéticas, CSV y GPX offline. Suavizado registrado y segmentación.
- Calibración acotada y robusta, diagnóstico de identificabilidad y RLS secuencial.
- M1 física, M2 Ridge, M3 Random Forest residual fijo y M4 CGPRA.
- Gates kNN y kNN + Mahalanobis regularizado + dispersión del ensemble.
- Intervalos conformales con rutas independientes. Pruebas ID, siete escenarios OOD y ablaciones.
- Monte Carlo: distribución de energía/SOC/autonomía y probabilidad de completar misión.
- Modelos CGPRA portables en CSV/JSON con replay verificado, accesibles por API/CLI/GUI.
- Energía predictiva con errores independientes observados, CRPS, cobertura y Brier
  de presupuesto energético. Diagnóstico explícito de transferencia OOD.
- API Python, CLI headless, GUI Tk ES/EN. Exports CSV/JSON/YAML/PNG/SVG/PDF.
- Sensibilidad OAT, Spearman, Morris y Sobol con diseños guardados y supuestos explícitos.
- Adaptación causal, conversión de telemetría, gráficas completas y bandas físicas de incertidumbre.

## Instalación

Python 3.11 o posterior. Python 3.12 recomendado para el build verificado en Windows.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,windows]"
.\.venv\Scripts\python.exe -m pytest -q
```

Tkinter debe estar disponible para la GUI. Viene con el instalador oficial Python
para Windows. El núcleo, la CLI y los experimentos no importan Tk.
Para reproducir el entorno comprobado: instalar primero `requirements-lock.txt`.

## Inicio rápido

En la GUI, **Ejemplos** abre nueve casos listos para cargar y ejecutar desde un
menú desplegable. **Tutorial** inicia una guía integrada de ocho pasos con acciones
para practicar, desde la primera ruta hasta la exportación. Ambos funcionan sin
conexión y en ES/EN. Véase el [manual de usuario](docs/user_manual.md).

**Cargar ejemplo → Simular** ejecuta el caso activo, incluida su calibración,
entrenamiento o incertidumbre cuando corresponda. El flujo ofrece únicamente
**Cargar ejemplo** y **Simular**.
La selección del desplegable se distingue del **Ejemplo activo**.

```powershell
.\.venv\Scripts\bikeenergylab.exe simulate configs/flat.yaml
.\.venv\Scripts\bikeenergylab.exe uncertainty configs/flat.yaml
.\.venv\Scripts\bikeenergylab.exe benchmark configs/benchmark.yaml
.\.venv\Scripts\bikeenergylab.exe experiments configs/benchmark.yaml
.\.venv\Scripts\bikeenergylab.exe calibrate datasets/synthetic_calibration.csv
.\.venv\Scripts\bikeenergylab.exe quality datasets/telemetry_example.csv
.\.venv\Scripts\bikeenergylab.exe gui
.\.venv\Scripts\bikeenergylab.exe train datasets/synthetic_calibration.csv
.\.venv\Scripts\bikeenergylab.exe predictive-validation configs/predictive_validation.yaml
.\.venv\Scripts\bikeenergylab.exe telemetry datasets/telemetry_example.csv
.\.venv\Scripts\bikeenergylab.exe sensitivity configs/flat.yaml --method sobol --samples 256
.\.venv\Scripts\bikeenergylab.exe prequential configs/adaptive_validation.yaml
```

Las carpetas de resultados se anuncian mediante logging. `--output` cambia el
destino. `--no-figures` desactiva figuras en simulate/uncertainty/benchmark/validación predictiva.
`train` anuncia una carpeta de modelo. Utilizar esa carpeta con `--model` en
`predict`, `simulate` o `uncertainty` para reutilizar el ajuste.

El paquete portátil `dist/BikeEnergyLab-1.0.0-windows-x64.zip` incluye el programa,
dependencias, manuales, configuraciones y ejemplos. Extraer la carpeta completa y
abrir `BikeEnergyLab.exe`. La CLI del ejecutable acepta los mismos comandos.
Véase [distribución Windows](docs/windows_distribution.md).
Incluye cinco documentos Word en español: [manual de usuario](docs/docx/Manual_de_usuario_BikeEnergyLab_1.0.0.docx),
[manual técnico](docs/docx/Manual_tecnico_BikeEnergyLab_1.0.0.docx),
[metodología científica](docs/docx/Metodologia_cientifica_BikeEnergyLab_1.0.0.docx),
[descripción del software](docs/docx/Descripcion_del_Software_BikeEnergyLab_1.0.0.docx) y
[título y funciones](docs/docx/Titulo_y_descripcion_de_funciones_BikeEnergyLab_1.0.0.docx).
Conservan capturas, ecuaciones editables, referencias y resultados sintéticos documentados.
La [matriz de funcionalidades](docs/completion.md) identifica implementación,
verificación y alcance científico de la entrega.

```python
from bikeenergylab import BikeModel, Config, Route

config = Config.from_yaml("configs/flat.yaml")
bike = BikeModel(config)
route = Route.synthetic(distance_m=10000, speed_mps=6.94, segments=100)
result = bike.simulate(route)
result.export("results")

prediction = bike.predict_mission_probability(
    route, n_samples=100, seed=42, reserve_soc=0.15,
    distributions={"environment.wind_mps": {
        "distribution": "normal", "mean": 0, "std": 1,
        "low": -5, "high": 5}},
)
```

`Route.from_gpx("route.gpx")` y `Route.from_csv("route.csv")` funcionan offline.
`bike.calibrate(observations)` recibe una lista de `Observation` y actualiza el modelo.

## Modelo científico y CGPRA

La pregunta central es si física calibrada más aprendizaje residual con gating
puede mejorar precisión y robustez frente a rutas y condiciones nuevas. La
hipótesis se contrasta con M1–M4, sin asumir superioridad.

\[
F=mgC_{rr}\cos\theta+mg\sin\theta+
\tfrac12\rho C_dA(v-v_{wind})|v-v_{wind}|+ma,\qquad P_{wheel}=Fv.
\]

\[
\hat E_{CGPRA}=\hat E_{phys}+\alpha(x)\hat r(x),\quad 0\le\alpha\le1.
\]

El gate disminuye la corrección con escaso soporte, distancia OOD o dispersión
residual alta. La confianza es un indicador de soporte, no una probabilidad de
que la predicción sea correcta. CGPRA es una metodología de trabajo provisional:
**no se reclama prioridad científica ni superioridad experimental**.

La dinámica es inversa con velocidad prescrita. `feasible=false` significa que la
misión no se completó o faltó potencia. La autonomía equivalente estacionaria
se distingue de la distancia obtenida al repetir una ruta hasta agotar la reserva.
Los cuantiles Monte Carlo dependen de las distribuciones elegidas. Los intervalos
conformales requieren exchangeability y no garantizan cobertura OOD.
La incertidumbre aprendida utiliza errores con signo de rutas reservadas y conserva
su sesgo. No transforma un intervalo conformal en una distribución. Su evaluación
del presupuesto energético se identifica por separado: no reconstruye trayectorias
SOC/corriente del modelo híbrido. Véase [metodología](docs/methodology.md).

## GUI

Quince secciones: Inicio, Bicicleta, Ciclista, Motor, Batería, Ruta, Ambiente,
Física, Calibración, Modelo híbrido, Incertidumbre, Simulación, Experimentos,
Resultados y Exportar. Selector ES/EN, tooltips, editor YAML para mapas/curvas,
ejecución en background y gráfica SOC. La GUI reutiliza la misma API.

## Experimentos y reproducibilidad

`experiments` ejecuta EXP-01–15. `examples/run_examples.py` ejecuta los once
ejemplos. Cada run incluye identificador único, fecha en America/Bogota, versión,
semilla, hashes SHA256 de entradas y fuentes, versiones de dependencias,
configuración, parámetros, predicciones, métricas y figuras. Los datasets
sintéticos y sus ecuaciones de generación se guardan junto al benchmark.

La entrada estándar de rutas es una tabla de intervalos `length_m, dt_s,
speed_mps, grade`. Las mediciones de sensores tienen esquema independiente.
Consulte [formatos](datasets/README.md), [metodología](docs/methodology.md),
[manual técnico](docs/technical_manual.md), [manual de usuario](docs/user_manual.md),
[referencias verificadas](docs/references.md) y [estado de validación](docs/validation.md).

## Ejecutable Windows

La carpeta **Entregables** contiene únicamente los cinco DOCX, el ZIP portátil
y `BikeEnergyLab-1.0.0-codigo-fuente.zip`. Extraiga el ZIP portátil fuera de
Entregables y abra `BikeEnergyLab/BikeEnergyLab.exe`. Conserve la carpeta extraída
completa con `_internal`. Los registros de revisión y hashes de entrega están
en `results/delivery-1.0.0`.

```powershell
.\scripts\build_windows.ps1
```

El build genera `dist/BikeEnergyLab/BikeEnergyLab.exe` y su directorio de
dependencias. Conservar la carpeta completa. Sin argumentos abre la GUI. Con
argumentos ofrece los mismos subcomandos que la CLI. El ejecutable es adicional
a la API y al paquete instalable. Consulte el manual técnico para verificarlo.

## Autores, citación y licencia

- Francisco Javier Burgos Flórez — fjburgosf@gmail.com.
- Juan Guillermo Popayán Hernández.

Metadatos de citación en [CITATION.cff](CITATION.cff). No se ha registrado DOI ni
publicado un artículo de validación. Historial en [CHANGELOG.md](CHANGELOG.md).
Los derechos permanecen reservados según [LICENSE](LICENSE). La selección de una
licencia de distribución abierta queda pendiente de los autores.
