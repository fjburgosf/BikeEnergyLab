# BikeEnergyLab 1.0.0 — alcance y trazabilidad

La versión 1.0.0 añade nueve ejemplos ejecutables desde un menú desplegable y un
tutorial contextual de ocho pasos en ES/EN. El catálogo se distribuye dentro del
paquete Python y del ejecutable. `tests/test_onboarding.py` comprueba los ejemplos;
la prueba GUI completa comprueba selección, guía, cambio de idioma y exportación.
La entrega unifica todos los componentes como versión 1.0.0. Se conserva la
identidad de los experimentos históricos; la distribución y la suite de
regresión se comprueban de nuevo tras unificar la versión.

Entrega funcional del framework científico de energía y autonomía. Autoría:
Francisco Javier Burgos Flórez y Juan Guillermo Popayán Hernández
(fjburgosf@gmail.com). CGPRA es una formulación provisional cuya utilidad se
somete a experimentos; su originalidad académica no se presume.

La versión integra simulación física, calibración adaptativa, aprendizaje residual,
compuerta de confianza, incertidumbre y evaluación reproducible. Las demostraciones
y datasets de la entrega son sintéticos. El alcance implementado está descrito
en metodología, manuales y protocolos; los modelos más detallados son extensiones
de fidelidad que requieren parámetros medidos.

| Funcionalidad | Implementación / acceso | Evidencia verificable |
|---|---|---|
| Pregunta, hipótesis, límites y método CGPRA | `docs/methodology.md`, README principal | Definiciones y ecuaciones; no afirmación de superioridad universal |
| Fuerzas de rodadura, pendiente, aero y aceleración | `physics`, `BikeModel.operating_profile` | Casos analíticos, viento con signo, aero ∝v³ |
| Potencia humana constante/temporal/condicional | `rider`, perfiles de ruta, GUI Rider | Aporte en pedales, eficiencia de transmisión, parada |
| Asistencia, potencia, torque y velocidad | `motor`, GUI Motor | Límites y demanda no satisfecha |
| Eficiencia constante o mapa | `motor.EfficiencyMap`, CSV/YAML | Interpolación, bordes, aviso de extrapolación |
| Control eléctrico y auxiliares | `model`, `battery` | Corriente/tensión, auxiliares no cubiertos |
| Batería energía/SOC/Thevenin RC | `battery`, GUI Battery | Balance, RC, conteo de coulombs, agotamiento exacto, SOC máximo |
| Temperatura y regeneración | Curvas de capacidad/resistencia y eficiencia; densidad aire; Regen opt-in | Pruebas térmicas, límites de carga, frenado y pérdidas |
| Rutas manuales, sintéticas, CSV y GPX | `routes`, GUI Route | Conservación longitud/tiempo, paradas con timestamps, filtro documentado |
| Segmentación uniforme/adaptativa | `Route.uniform`, `Route.adaptive`, `Route.subdivide` | Conservación de eventos y contraste numérico |
| Superficie, pendiente y coordenadas | Perfiles, tabla y vista de ruta | Gráficas elevación/pendiente/velocidad/superficie; mapa opcional |
| Calibración offline e identificabilidad | `calibration.calibrate`, CLI calibrate | Recuperación de verdad sintética y advertencias de confusión |
| Adaptación física y residual causal | `CGPRAModel.adapt`, CLI/GUI adapt | RLS acotado; rollback ante fallos; comparación prequential |
| Residuos y CGPRA | `residual.CGPRAModel`, CLI train/predict | M1–M4; compuerta kNN y Mahalanobis/ensemble |
| Error/intervalos calibrados | `calibrate_intervals` | Grupos disjuntos, conformal finito, errores firmados, invalidación al adaptar |
| OOD y ablaciones | `experiments.benchmark` | ID + siete shifts, dos gates, cuatro componentes ablacionados |
| Incertidumbre paramétrica/operacional | `uncertainty.monte_carlo` | Semillas, límites, correlaciones explícitas, ruido altimétrico |
| Autonomía y misión | `BikeModel.predict_range`, `predict_mission_probability` | Depleción física, reserva, factibilidad, censura, error Monte Carlo |
| Energía predictiva y presupuesto | `predictive_workflow.md`, CLI uncertainty --model | CRPS, cobertura, Brier, casos no identificados; separación de misión dinámica |
| Bandas físicas de trayectoria | `UncertaintyResult.trajectory_bands` | Cuantiles SOC/Wh; número de muestras que llegan; sin extrapolar agotamiento |
| Sensibilidad ocho parámetros | OAT, Spearman, Morris, Sobol; GUI/CLI/API | Efectos lineales y referencia Ishigami; diseño y bootstrap guardados |
| Experimentos EXP-01–15 | `experiments.suite`, GUI/CLI experiments | Sweeps, calibración, baselines, OOD, autonomía y misión |
| Validación por semillas y deriva | `experiments.predictive`, `experiments.adaptive` | Entrenamiento/calibración/test separados; causalidad de predicción |
| Calidad y telemetría | CLI quality/telemetry, GUI Calibration, `io.telemetry` | V·I integrado; tiempos en segundos; perfil/mediciones originales preservados |
| GUI offline ES/EN | Quince módulos, ayudas, scroll, pestañas y herramientas de figuras | Smoke de cálculos físicos/híbridos, MC, idiomas y controles |
| API/CLI/headless | Paquete Python, `python -m bikeenergylab` | Pruebas de entrada/salida y comandos; núcleo sin dependencia de GUI activa |
| Gráficas y exportación | Potencias, SOC, Wh/km, balance, bandas, residuos, ajuste, OOD | PNG/SVG/PDF; render estático y comparación de tablas |
| Reproducibilidad y modelos portables | EXP únicos; config/seed/data/source hashes; CSV/JSON replay | Integridad, modelo portable, referencia numérica entre runtimes |
| Tests, logging y manejo de errores | `tests`, logger CLI, logs por EXP | Analítica, estados inválidos, regresiones y workflows completos |
| Documentación y atribución | README, manuales, metodología, referencias, CITATION, changelog, LICENSE | Fuentes primarias verificadas; identificación de supuestos |
| Instalación y Windows | Wheel/sdist, lock, scripts; EXE + ZIP portátil | Entorno aislado, EXE y comparación de predicciones/exports |

## Alcance científico de la entrega

La verificación numérica y la validación sintética permiten estudiar y refutar
hipótesis dentro de los supuestos implementados. Se conservan resultados desfavorables:
en validación predictiva, las distribuciones aprendidas en ID pierden cobertura
bajo ciertos shifts térmicos/combinados. La compuerta α es un peso residual, no
la probabilidad de que una predicción sea correcta.

La telemetría real puede importarse, pero no se dispone de mediciones de campo
en esta entrega. Precisión real, robustez bajo deriva medida, parámetros independientes
de motor/batería y prioridad académica necesitan evidencia experimental externa.
La agregación residual por ruta no identifica una corrección dinámica de SOC;
las trayectorias y misión siguen el modelo físico explícito.

## Verificación de distribución

`scripts/validate_release.ps1` repite la validación local y produce artefactos.
`scripts/verify_distribution.py` verifica wheel aislado y ejecutable congelado,
con identidad de código y replay. `results/release_verification.json` y
`results/README.md` localizan los resultados de la versión; las entregas anteriores
se conservan como historial con su propia identidad.

El ZIP conserva `_internal`, configuraciones, manuales, ejemplos, datasets y
avisos de dependencias. La licencia del proyecto mantiene los derechos reservados
de los autores. Las fuentes y los documentos se mantienen en https://github.com/fjburgosf/BikeEnergyLab.
