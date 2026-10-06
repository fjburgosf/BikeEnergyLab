# Manual técnico de BikeEnergyLab

## 1. Introducción

### 1.1 Propósito del software

BikeEnergyLab 1.0.0 modela energía, autonomía y misión de bicicletas eléctricas con física explícita, calibración y aprendizaje residual. Este manual explica arquitectura y procedimientos reproducibles para desarrolladores e investigadores.

### 1.2 Contexto y alcance

La revisión ilustrada del 6 de octubre de 2026 conserva la identidad de algoritmos y resultados históricos. Los ejemplos son sintéticos. Repositorio: https://github.com/fjburgosf/BikeEnergyLab. Contacto: fjburgosf@gmail.com.

## 2. Arquitectura del sistema

### 2.1 Arquitectura y responsabilidades

BikeEnergyLab separa la configuración, los cálculos numéricos, los datos y la interfaz. La API y la CLI permiten ejecutar experimentos sin Tk ni interacción gráfica. La GUI adapta los mismos componentes y presenta los resultados; no introduce un segundo modelo físico. Las ecuaciones y sus supuestos se desarrollan en el documento Metodología científica de BikeEnergyLab.

| Componente | Responsabilidad |
| --- | --- |
| config.py | Dataclasses, lectura YAML estricta, validación y copias de parámetros |
| routes | Intervalos, CSV y GPX, paradas, suavizado registrado y segmentación |
| physics | Fuerzas longitudinales, viento con signo, densidad del aire y unidades SI |
| motor | Eficiencia constante o mapas rectangulares interpolados |
| battery | Estado energético, SOC y circuito equivalente Thevenin de una rama RC |
| model.py | Perfil operativo, demanda física, integración de batería y balances |
| calibration | Ajuste acotado, identificabilidad práctica y actualización secuencial RLS |
| residual | M1 a M4, características, compuertas, intervalos y replay del modelo |
| uncertainty | Monte Carlo físico, misión, autonomía y errores predictivos opcionales |
| metrics | MAE, RMSE, R², intervalos y CRPS empírico |
| experiments | Verdad sintética, escenarios ID y OOD, ablaciones y EXP 01 a 15 |
| io | Calidad de datos, telemetría, exportación y metadatos de reproducción |
| visualization | Figuras PNG, SVG y PDF mediante Matplotlib sin GUI |
| gui | Adaptador Tk, ayudas ES y EN, ejemplos y tutorial integrado |
| cli.py | Despacho de comandos sin conexión y registro de eventos |

El flujo de cálculo parte de la ruta prescrita, construye el perfil operativo, obtiene la demanda eléctrica, integra los límites de batería y registra las contribuciones realizadas. La factibilidad de potencia y la finalización de la ruta se informan por separado. La predicción de demanda de la ruta completa no debe confundirse con la energía consumida hasta el agotamiento.

## 3. Componentes del software

### 3.1 Clases públicas y uso de la API

**Config** expone from_yaml, from_dict, changed y validate. Rechaza secciones desconocidas y atributos mal escritos. **Route** ofrece synthetic, from_csv, from_gpx, from_elevation, subdivide, uniform y adaptive. Las operaciones de segmentación conservan las distancias y registran las aproximaciones utilizadas.

**BikeModel** ofrece operating_profile, predict_energy, simulate, calibrate, predict_range y predict_mission_probability. **SimulationResult.export** conserva configuración, series, resumen, figuras y metadatos en una carpeta de ejecución nueva. Los métodos numéricos no necesitan importar la GUI.

**Observation(route, energy_wh, config, group, weight)** vincula una ruta con su energía terminal observada, condiciones operativas y grupo independiente. **CalibrationResult** contiene parámetros ajustados, residuos, covarianza aproximada y diagnósticos de identificabilidad. Los grupos corresponden a rutas completas; los segmentos de una misma ruta no son réplicas independientes.

**CGPRAModel** expone fit, predict, calibrate_intervals, adapt, save, load y annotate_simulation. **ConfidenceGate** permite fit y evaluate. La opción physical_energy_wh de predict conserva una demanda física externa, por ejemplo una realización de parámetros muestreados en Monte Carlo.

```python
from bikeenergylab import Config
from bikeenergylab.experiments import generate_observations
from bikeenergylab.residual import CGPRAModel

train = generate_observations(60, 42, prefix="train")
held = generate_observations(30, 43, prefix="interval")
test = generate_observations(15, 44, scenario="OOD-Wind", prefix="test")
model = CGPRAModel(Config(), seed=42).fit(train)
model.calibrate_intervals(held)
prediction = model.predict(test, model="M4", coverage=0.95)
```

### 3.2 Configuración y parámetros físicos

Los valores iniciales son supuestos editables. La masa total incluye bicicleta, ciclista y carga. Crr es un escalar calibrable para la superficie default o un coeficiente indicado por superficie. CdA combina área frontal y coeficiente aerodinámico. La potencia humana se define en pedales y la eficiencia de transmisión transforma su contribución a la rueda.

El motor admite asistencia demand o proportional, límite mecánico, torque equivalente, velocidad de corte y eficiencia constante o mapa CSV. La coordenada de mapa usa velocidad angular equivalente v/r; una curva de rotor de motor central necesita transformarse antes de utilizarse. Los puntos fuera del mapa se acotan a su frontera y quedan señalados.

La batería admite energy, soc y ecm. Energy y soc representan la misma contabilidad energética en esta versión. ECM añade capacidad Ah, OCV, resistencias, una rama RC y restricciones de voltaje y corriente. Cambiar Wh nominales no modifica automáticamente la capacidad Ah del ECM. Las curvas térmicas requieren datos de la batería concreta; si faltan, no se inventa una degradación por temperatura.

| Magnitud | Unidad o convención |
| --- | --- |
| Distancia y duración del intervalo | m y s |
| Velocidad solicitada | m/s a lo largo de la vía |
| Pendiente grade | Elevación dividida por distancia horizontal |
| Viento positivo | Viento posterior en m/s |
| Potencia y energía terminal | W y Wh |
| Consumo por distancia | Wh/km |
| SOC y nivel de asistencia | Fracciones entre 0 y 1 |
| Crr y CdA | Adimensional y m² respectivamente |

## 4. Adquisición y procesamiento de datos

### 4.1 Rutas y telemetría

Los CSV de ruta requieren length_m, dt_s, speed_mps y grade. Se verifica la relación entre distancia, velocidad y duración; no se corrigen silenciosamente inconsistencias. Las columnas temporales de viento, temperatura, potencia humana u otras condiciones tienen prioridad sobre los valores escalares. Una distribución escalar incompatible con un perfil temporal se rechaza para evitar una propagación de incertidumbre ficticia.

Los GPX con tiempos permiten derivar velocidades y conservar paradas. Sin tiempos, se requiere una velocidad supuesta. Las discontinuidades entre segmentos necesitan preparación explícita. El filtro mediano de elevaciones y la segmentación quedan registrados. El primer intervalo no se trata como una aceleración inventada desde reposo.

**io.telemetry.load_telemetry** valida grupos, deriva velocidad de distancia y tiempo, e integra potencia terminal V por I mediante trapecios entre muestras. La duración se convierte a segundos independientemente de la resolución del datetime. El resultado incluye observaciones exportables, procedencia de la conversión y advertencias de calidad.

## 5. Flujo de operación del sistema

### 5.1 Interfaz gráfica y tareas en segundo plano

Tk gestiona quince secciones. Un ejecutor con un trabajador realiza los cálculos; el hilo principal actualiza widgets y dibuja resultados. Durante un cálculo se bloquean los controles de edición. Los errores se presentan y se registran; no se fabrican resultados exitosos.

El catálogo de nueve ejemplos y el tutorial de ocho pasos están incluidos en gui.onboarding. Funcionan en la instalación Python y en el ejecutable, sin depender de scripts externos. El tutorial conserva el paso al cambiar ES y EN. Cargar un ejemplo reemplaza la configuración, el resultado y el modelo activos, con una explicación visible en Inicio.

El ejemplo cargado se registra por separado de la selección del desplegable. El flujo ofrece Cargar ejemplo y Simular. Simular despacha el flujo activo: física, calibración, incertidumbre o entrenamiento híbrido inicial. Un modelo híbrido ya entrenado se reutiliza; abrir otro YAML descarta el contexto del ejemplo.

Las pruebas GUI utilizan el bucle real de eventos de Tk y fallan ante errores de callbacks o limpieza. Los ciclos obsoletos de Tk y Matplotlib se recolectan en el hilo principal, también al cerrar. Se verifica el recorrido de la guía hasta exportar figuras PNG, SVG y PDF.

### 5.2 Artefactos y reproducción

Cada exportación crea una carpeta EXP nueva. Conserva configuración YAML, tablas CSV, resumen JSON, semilla, versiones de dependencias, fecha de Bogotá y hashes SHA256. Las rutas importadas y los mapas utilizados se copian para permitir reproducción portátil. La CLI devuelve código 2 ante errores previstos de entrada o archivo y muestra trazas de fallos inesperados.

Los modelos se guardan como datos CSV y JSON con comprobaciones de integridad y predicciones de referencia. load reconstruye el ajuste y verifica el replay. Se debe conservar la carpeta completa; no basta con copiar un JSON aislado. En el ejecutable se incorpora la misma identidad de fuentes que en el modo Python.

## 6. Algoritmos y métodos implementados

### 6.1 Calibración y aprendizaje residual

La calibración minimiza errores de energía por rutas completas con pesos y límites explícitos. Por defecto ajusta Crr y CdA. Para ajustar más parámetros, hacen falta límites razonables y variación operativa que permita distinguir sus efectos. Se revisan rango del Jacobiano, valores singulares, condición, colinealidad y soluciones en fronteras. La covarianza local es una aproximación y no un posterior calibrado.

M1 utiliza física calibrada; M2 utiliza datos; M3 añade el residual completo; M4 aplica CGPRA y su peso alpha. El objetivo residual está expresado en Wh/km. Las características resumen velocidad, pendientes, aceleración, viento, temperatura, aporte humano, masa, asistencia, Crr y variación de velocidad. La pérdida de información temporal por agregación es un límite de fidelidad.

El entrenamiento, la calibración de intervalos y la prueba usan grupos de rutas distintos. Los intervalos conformales se ajustan con errores absolutos por distancia. Su interpretación depende de intercambiabilidad; el soporte OOD y el peso alpha no garantizan exactitud ni cobertura.

### 6.2 Adaptación y evaluación causal

**model.adapt(new_observation)** actualiza los parámetros físicos mediante RLS acotado y vuelve a construir los residuos respecto a la física actualizada. Solo acepta rutas nuevas. Cada actualización invalida cuantiles conformales y muestras previas de error. Hasta disponer de una calibración independiente fresca, se conserva la predicción puntual.

Las operaciones fit y adapt trabajan de forma transaccional. Si falla una etapa, el objeto original mantiene su estado válido. Las observaciones utilizadas para intervalos no se reutilizan como nuevas rutas de adaptación ni como una nueva calibración posterior.

**experiments.adaptive.prequential_evaluate** compara modelos congelados y adaptativos. Predice cada ruta antes de consumir su energía observada. El protocolo sintético permite verificar esta causalidad, pero no establece eficacia ante deriva real ni identificación universal de parámetros.

```powershell
bikeenergylab adapt CARPETA_MODELO nuevas_rutas.csv --output resultados
bikeenergylab predict configs/flat.yaml --model CARPETA_ADAPTADA --point-only
```

### 6.3 Incertidumbre y sensibilidad

Monte Carlo propaga las distribuciones físicas configuradas y mantiene separado el análisis opcional de errores predictivos CGPRA. La probabilidad física de misión exige completar la ruta, disponer de potencia y terminar por encima de la reserva. El análisis energy_budget_probability evalúa un presupuesto energético; no corrige dinámicamente corriente, voltaje o SOC.

Las bandas de trayectoria usan el avance normalizado y contabilizan cuántas realizaciones llegan a cada punto. No extrapolan después del agotamiento. La autonomía que supera el horizonte se informa como censurada; una trayectoria imposible por potencia no genera una autonomía admisible.

**uncertainty.global_sensitivity.physical_sensitivity** ofrece Morris, Sobol y Spearman con semilla y dominios explícitos. **analyze_global** admite cualquier respuesta escalar. OAT proporciona cambios locales. Los índices de Sobol ordinarios requieren entradas independientes; no se trasladan automáticamente a una distribución conjunta correlacionada de Monte Carlo.

```powershell
bikeenergylab sensitivity configs/flat.yaml --method morris --samples 16
bikeenergylab sensitivity configs/flat.yaml --method sobol --samples 256
```

## 7. Restricciones y límites

### 7.1 Identidad de la entrega y límites

{{SOURCE}}

El núcleo fuera de la GUI coincide con el wheel de la revisión científica histórica del 4 de octubre de 2026, conservado en results/history. La validación científica histórica conserva sus propios hashes y resultados; los cambios de interfaz no se presentan como nuevos experimentos. La verificación actual está en results/release_verification.json y la histórica en results/release_verification_1.0.0.json.

La precisión con bicicletas reales, la calibración de probabilidades, los parámetros independientes de hardware y la novedad académica requieren evidencia adicional. El software utiliza dinámica inversa con velocidad prescrita. Los residuos por ruta no identifican una corrección temporal aprendida de SOC, corriente o voltaje.

## 8. Despliegue y ejecución

### 8.1 Pruebas y distribución Windows

La versión 1.0.0 pasó 80 pruebas, lint y formato, y el recorrido GUI en español e inglés. La instalación wheel aislada y el ejecutable se comprobaron con replay M1 a M4, exportación híbrida, Monte Carlo predictivo, sensibilidad, telemetría, adaptación y tutorial. Las predicciones coincidieron con tolerancia de 1e-8 y pip check no detectó dependencias rotas.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m bikeenergylab gui --smoke-test
.\.venv\Scripts\python.exe scripts/build_package.py
.\scripts\build_windows.ps1
```

PyInstaller genera una carpeta onedir. El ejecutable necesita conservar _internal con las DLL, recursos Tk y Matplotlib, metadatos y dependencias. Los backends SVG y PDF y los datos de scipy.stats requeridos por Sobol se incluyen explícitamente. El ZIP incorpora manuales, configuraciones, ejemplos, datos sintéticos, avisos de terceros y SHA256SUMS.json. No hay instalador ni firma digital.

Las fuentes, el lock y los scripts permiten repetir el proceso; no se promete igualdad binaria entre builds. La revisión ampliada invoca los botones reales de Tk con respuestas controladas de diálogos, incluyendo archivos, ejemplos, tutorial, modelos, sensibilidad, benchmark, EXP 01 a 15 y exportación. Otra máquina Windows y una revisión de todos los diálogos nativos aportarían evidencia adicional.

La carpeta Entregables reúne BikeEnergyLab.exe con _internal, los cinco DOCX, el ZIP portátil, un ZIP de código fuente y los registros de verificación. PUBLICACION_GITHUB.json informa si el código se ha subido y registra el repositorio y el commit; el código se encuentra en el repositorio público https://github.com/fjburgosf/BikeEnergyLab.

## 9. Glosario de términos

| Término | Definición operativa |
| --- | --- |
| Wh y Wh/km | Energía terminal y consumo por distancia |
| SOC | Fracción de carga sobre capacidad efectiva |
| Crr y CdA | Rodadura y área aerodinámica equivalente |
| M1 M2 M3 M4 | Física calibrada, datos, residual fijo y CGPRA |
| Alpha | Peso residual; no probabilidad de acierto |
| ID y OOD | Dominio y cambios de distribución |
| Intervalo conformal | Conjunto calibrado con rutas retenidas |
| Reserva | SOC mínimo para una misión exitosa |
| Censura | Horizonte termina antes del agotamiento |
| Replay | Predicciones de referencia del modelo reconstruido |
| RLS | Actualización secuencial de parámetros |
| ECM | Circuito equivalente de una rama RC |
| SHA256 | Identidad; no firma de autenticidad |
