# Manual técnico de BikeEnergyLab

## 1. Introducción

### 1.1 Propósito del software

BikeEnergyLab 1.0.0 modela energía, autonomía y misión de bicicletas eléctricas con física explícita, calibración y aprendizaje residual. Este manual explica arquitectura y procedimientos reproducibles para desarrolladores e investigadores.

### 1.2 Contexto y alcance

La revisión de auditoría del 8 de octubre de 2026 conserva la identidad de algoritmos y resultados históricos. Los ejemplos son sintéticos. Contacto: fjburgosf@gmail.com.

### 1.3 Pregunta de investigación y alcance

La pregunta es si la física calibrada, el aprendizaje residual y una compuerta de confianza pueden mejorar la predicción energética ante nuevas rutas, ciclistas y condiciones. La hipótesis contrastable es que CGPRA mantiene o mejora el error respecto a M1, M2 y M3, especialmente ante cambios de distribución. Los protocolos permiten refutarla. El nombre del método no establece superioridad, novedad ni aceptación académica.

La entrega utiliza datos sintéticos con verdad física y discrepancia declaradas. Los resultados que siguen pertenecen a esos protocolos, no a mediciones de una bicicleta real. La versión 1.0.0 incluye los ejemplos y el tutorial. Su núcleo numérico conserva el comportamiento de la revisión científica histórica del 4 de octubre de 2026. Se conserva la identidad de cada experimento para distinguirlos de las pruebas de software.

## 2. Arquitectura del sistema

### 2.1 Arquitectura y responsabilidades

BikeEnergyLab separa la configuración, los cálculos numéricos, los datos y la interfaz. La API y la CLI permiten ejecutar experimentos sin Tk ni interacción gráfica. La GUI adapta los mismos componentes y presenta los resultados. No introduce un segundo modelo físico. Las ecuaciones y sus supuestos se desarrollan en el capítulo 6 de este manual técnico.

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

**Observation(route, energy_wh, config, group, weight)** vincula una ruta con su energía terminal observada, condiciones operativas y grupo independiente. **CalibrationResult** contiene parámetros ajustados, residuos, covarianza aproximada y diagnósticos de identificabilidad. Los grupos corresponden a rutas completas. Los segmentos de una misma ruta no son réplicas independientes.

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

El motor admite asistencia demand o proportional, límite mecánico, torque equivalente, velocidad de corte y eficiencia constante o mapa CSV. La coordenada de mapa usa velocidad angular equivalente v/r. Una curva de rotor de motor central necesita transformarse antes de utilizarse. Los puntos fuera del mapa se acotan a su frontera y quedan señalados.

La batería admite energy, soc y ecm. Energy y soc representan la misma contabilidad energética en esta versión. ECM añade capacidad Ah, OCV, resistencias, una rama RC y restricciones de voltaje y corriente. Cambiar Wh nominales no modifica automáticamente la capacidad Ah del ECM. Las curvas térmicas requieren datos de la batería concreta. Si faltan, no se inventa una degradación por temperatura.

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

### 3.3 Unidades y convenciones

| Símbolo o magnitud | Definición y unidad |
| --- | --- |
| m y g | Masa total en kg y gravedad en m/s² |
| v y a | Velocidad longitudinal en m/s y aceleración en m/s² |
| w y vrel | Viento longitudinal y velocidad relativa en m/s |
| grade y theta | Elevación sobre horizontal y ángulo de pendiente en radianes |
| Crr y CdA | Rodadura adimensional y área por coeficiente aerodinámico en m² |
| rho y p | Densidad del aire en kg/m³ y presión en Pa |
| P y E | Potencia en W y energía en Wh |
| SOC | Fracción de carga sobre la capacidad efectiva configurada |
| L | Longitud de la ruta en km en las ecuaciones de residuos |

El movimiento positivo avanza sobre la vía. El viento positivo es posterior. Una pendiente 0.03 equivale al 3%. El ángulo se obtiene con atan(grade). La aceleración inferida usa diferencias entre intervalos y no inventa una salida desde reposo en la primera muestra. Si se dispone de aceleración medida, puede suministrarse explícitamente.

## 4. Adquisición y procesamiento de datos

### 4.1 Rutas y telemetría

Los CSV de ruta requieren length_m, dt_s, speed_mps y grade. Se verifica la relación entre distancia, velocidad y duración. No se corrigen silenciosamente inconsistencias. Las columnas temporales de viento, temperatura, potencia humana u otras condiciones tienen prioridad sobre los valores escalares. Una distribución escalar incompatible con un perfil temporal se rechaza para evitar una propagación de incertidumbre ficticia.

Los GPX con tiempos permiten derivar velocidades y conservar paradas. Sin tiempos, se requiere una velocidad supuesta. Las discontinuidades entre segmentos necesitan preparación explícita. El filtro mediano de elevaciones y la segmentación quedan registrados. El primer intervalo no se trata como una aceleración inventada desde reposo.

**io.telemetry.load_telemetry** valida grupos, deriva velocidad de distancia y tiempo, e integra potencia terminal V por I mediante trapecios entre muestras. La duración se convierte a segundos independientemente de la resolución del datetime. El resultado incluye observaciones exportables, procedencia de la conversión y advertencias de calidad.

## 5. Flujo de operación del sistema

### 5.1 Interfaz gráfica y tareas en segundo plano

Tk gestiona quince secciones. Un ejecutor con un trabajador realiza los cálculos. El hilo principal actualiza widgets y dibuja resultados. Durante un cálculo se bloquean los controles de edición. Los errores se presentan y se registran. No se fabrican resultados exitosos.

El catálogo de nueve ejemplos y el tutorial de ocho pasos están incluidos en gui.onboarding. Funcionan en la instalación Python y en el ejecutable, sin depender de scripts externos. El tutorial conserva el paso al cambiar ES y EN. Cargar un ejemplo reemplaza la configuración, el resultado y el modelo activos, con una explicación visible en Inicio.

El ejemplo cargado se registra por separado de la selección del desplegable. El flujo ofrece Cargar ejemplo y Simular. Simular despacha el flujo activo: física, calibración, incertidumbre o entrenamiento híbrido inicial. Un modelo híbrido ya entrenado se reutiliza. Abrir otro YAML descarta el contexto del ejemplo.

Las pruebas GUI utilizan el bucle real de eventos de Tk y fallan ante errores de callbacks o limpieza. Los ciclos obsoletos de Tk y Matplotlib se recolectan en el hilo principal, también al cerrar. Se verifica el recorrido de la guía hasta exportar figuras PNG, SVG y PDF.

### 5.2 Artefactos y reproducción

Cada exportación crea una carpeta EXP nueva. Conserva configuración YAML, tablas CSV, resumen JSON, semilla, versiones de dependencias, fecha de Bogotá y hashes SHA256. Las rutas importadas y los mapas utilizados se copian para permitir reproducción portátil. La CLI devuelve código 2 ante errores previstos de entrada o archivo y muestra trazas de fallos inesperados.

Los modelos se guardan como datos CSV y JSON con comprobaciones de integridad y predicciones de referencia. load reconstruye el ajuste y verifica el replay. Se debe conservar la carpeta completa. No basta con copiar un JSON aislado. En el ejecutable se incorpora la misma identidad de fuentes que en el modo Python.

## 6. Algoritmos y metodología científica

### 6.1 Fuerzas y potencia longitudinal

{{EQ:forces}}

{{EQ:wheel}}

{{EQ:density}}

En estas expresiones, grade es elevación dividida por avance horizontal, p se expresa en Pa y T en °C. La forma con signo de la fuerza aerodinámica permite que un viento posterior más rápido que la bicicleta aporte fuerza favorable. Elevar al cuadrado la velocidad relativa sin conservar el signo sería incorrecto. A velocidad cero, la potencia longitudinal es cero. La fricción estática queda fuera del modelo y la fuerza de rodadura se anula en reposo.

Se usa dinámica inversa con velocidad prescrita. El modelo calcula lo necesario para seguir ese perfil y señala demanda no satisfecha cuando los límites lo impiden. No resuelve una trayectoria de velocidad libre. Se omiten viento transversal, inercia rotacional y dinámica del cambio de marchas. El suavizado y la unión de segmentos son aproximaciones. Hace falta comprobar convergencia de la segmentación.

### 6.2 Ciclista, transmisión y motor

{{EQ:power}}

La masa total reúne bicicleta, ciclista y carga. Crr puede calibrarse para la superficie default o definirse por superficie. Los valores iniciales de rodadura, CdA y transmisión son supuestos, no constantes universales. La contribución humana se limita a la demanda positiva y la potencia sobrante no carga la batería.

La potencia humana admite un valor constante, columnas temporales o un modo condicionado por cadencia, pendiente y fatiga. Los coeficientes iniciales no añaden fatiga ni ganancia por pendiente. Este modo es operativo y no constituye un modelo fisiológico validado.

La asistencia demand ordena una fracción de la demanda. Proportional depende del aporte humano multiplicado por la relación de asistencia. Se aplican límites mecánicos, torque equivalente y corte de velocidad configurables. No se supone una normativa territorial. La eficiencia usa una constante o un mapa bilineal en velocidad angular equivalente y torque. Se informa si un punto queda fuera de su dominio.

### 6.3 Batería energética y estado de carga

{{EQ:capacity}}

{{EQ:soc}}

Efull es la capacidad nominal por la fracción usable y un multiplicador térmico empírico, si existe. SOC se define sobre esa base efectiva. Con 500 Wh nominales, fracción 0.95 y SOC de 0.90 a 0.10 hay 380 Wh disponibles. Energy y soc son representaciones equivalentes de esta contabilidad en la versión actual.

La actualización de SOC usa potencia terminal con signo positivo de descarga, Δt en s y Efull en Wh. Si la temperatura cambia, se usa una aproximación de capacidad efectiva local. No representa retraso térmico ni liberación reversible de capacidad. Sin curvas empíricas no se introduce una pérdida de capacidad por frío. Fuera del dominio de una curva definida se rechaza la extrapolación.

### 6.4 Circuito equivalente de batería

{{EQ:ecm}}

El ECM Thevenin de una rama RC usa Qeffective en Ah e I en A. Resuelve potencia terminal P igual a V por I mediante la raíz de corriente pequeña estable. Limita corriente de descarga, corriente de carga y voltaje. La carga se integra con capacidad efectiva en Ah y la rama RC se actualiza exactamente para corriente constante en cada subpaso.

La energía terminal y la potencia química OCV por I son distintas y se exportan por separado. Ah requiere caracterización propia. Cambiar Wh no modifica automáticamente la capacidad de conteo de carga. OCV, R0, R1 y C1 iniciales son ilustrativos. El voltaje se evalúa al inicio del subpaso. Reducir dt y comprobar convergencia es necesario. No se modelan envejecimiento, electroquímica detallada ni temperatura interna.

### 6.5 Límites, regeneración y balance

La batería detiene o acorta el subpaso al alcanzar el límite de energía o SOC. La regeneración está desactivada por defecto. Activarla requiere hardware capaz, frenado o descenso, velocidad mínima, límite eléctrico y margen de corriente y SOC para cargar. Los auxiliares pueden consumir potencia regenerada incluso con la batería llena.

{{EQ:terminal}}

El balance completo suma contribuciones mecánicas con signo, pérdidas de transmisión y motor, conversión regenerativa, disipación de frenado, auxiliares y demanda no satisfecha. energy_balance_error_w comprueba la identidad implementada. La recuperación se informa aparte. No debe restarse de nuevo a la energía de pendiente, porque duplicaría el efecto del descenso.

### 6.6 Calibración e identificabilidad

{{EQ:fit}}

El ajuste usa least_squares acotado y rutas completas con pesos wi. Los parámetros por defecto son Crr y CdA. Ajustar eficiencia, potencia humana o auxiliares requiere límites y excitación independiente suficientes. Las condiciones de cada observación se conservan y solo se transfieren los parámetros ajustados.

La identificabilidad práctica se examina con Jacobiano normalizado por amplitud de parámetros, rango SVD, condición y coseno entre columnas. Parámetros en fronteras, sensibilidades colineales o rango insuficiente deben informarse. Un residuo pequeño no demuestra identificación física. La covarianza local aproximada no constituye un posterior calibrado bajo deficiencia de rango o pérdidas robustas.

El experimento de recuperación utiliza cero discrepancia y cero ruido. El benchmark también introduce discrepancia estructural: los parámetros físicos pueden absorber sesgo residual. Deben analizarse errores y diagnósticos junto con los valores de parámetros.

### 6.7 Aprendizaje residual y modelos comparados

{{EQ:residual}}

{{EQ:models}}

r es el residuo en Wh/km y L la distancia en km, de modo que la corrección final queda en Wh. M2 usa Ridge escalado y el aprendizaje residual usa Random Forest con semilla. No se presupone que una arquitectura profunda mejore este problema.

Las características incluyen medias temporales de velocidad, velocidad cúbica, aceleración, pendiente con signo y positiva, viento, temperatura, potencia humana, masa, asistencia, Crr y variación de velocidad. Estos resúmenes descartan parte de la secuencia de la ruta. Un piso numérico de escala 1e-6 evita que redondeo en columnas casi constantes produzca soporte OOD artificialmente extremo. No representa precisión de sensor.

### 6.8 Compuerta de confianza y soporte OOD

{{EQ:gate}}

La compuerta simple normaliza distancias kNN mediante el percentil 95 de distancias de entrenamiento dejando fuera el punto propio. La avanzada usa el mayor soporte normalizado entre kNN y Mahalanobis con covarianza regularizada, y penaliza dispersión de árboles. n es el número de rutas de entrenamiento, d el soporte normalizado y u la dispersión normalizada por la desviación de residuos de entrenamiento. La simple usa u igual a cero.

Los coeficientes se fijan antes de probar. La dispersión de árboles es heurística y no una desviación bayesiana. Alpha es un peso residual, no una probabilidad de acierto. Un alpha pequeño devuelve la predicción hacia la física calibrada, que también puede tener sesgo. La distancia OOD no detecta todos los cambios condicionales.

### 6.9 Adaptación y evaluación causal

**model.adapt(new_observation)** actualiza los parámetros físicos mediante RLS acotado y vuelve a construir los residuos respecto a la física actualizada. Solo acepta rutas nuevas. Cada actualización invalida cuantiles conformales y muestras previas de error. Hasta disponer de una calibración independiente fresca, se conserva la predicción puntual.

Las operaciones fit y adapt trabajan de forma transaccional. Si falla una etapa, el objeto original mantiene su estado válido. Las observaciones utilizadas para intervalos no se reutilizan como nuevas rutas de adaptación ni como una nueva calibración posterior.

**experiments.adaptive.prequential_evaluate** compara modelos congelados y adaptativos. Predice cada ruta antes de consumir su energía observada. El protocolo sintético permite verificar esta causalidad, pero no establece eficacia ante deriva real ni identificación universal de parámetros.

```powershell
bikeenergylab adapt CARPETA_MODELO nuevas_rutas.csv --output resultados
bikeenergylab predict configs/flat.yaml --model CARPETA_ADAPTADA --point-only
```

### 6.10 Intervalos y propagación de incertidumbre

{{EQ:conformal}}

La calibración conformal usa grupos independientes y errores absolutos en Wh/km. El rango del cuantil k usa n rutas de calibración y cobertura c. La función ceil redondea al entero superior. Para 95% se necesitan al menos 19 rutas. Cada modelo usa sus propios errores retenidos. Las garantías finitas requieren intercambiabilidad, por lo que la cobertura OOD se mide y no se garantiza.

Monte Carlo muestrea distribuciones físicas configuradas, normales truncadas o uniformes, y admite una distribución gaussiana conjunta acotada. La covarianza local de calibración, si se utiliza, conserva su carácter aproximado. Se pueden propagar errores de elevación con el filtro mediano registrado. Los perfiles temporales tienen prioridad. Se rechaza incertidumbre escalar que no pudiera afectar al perfil.

Los errores firmados retenidos CGPRA pueden añadirse a la demanda de ruta completa como un análisis predictivo separado. Ese muestreo necesita calibración vigente y supuestos de transferencia de error. El presupuesto energético no identifica una corrección dinámica de SOC, voltaje o corriente. Un conjunto conformal por sí solo no define una distribución para calcular CRPS.

### 6.11 Misión, autonomía y trayectorias

{{EQ:mission}}

El éxito requiere ruta completa, potencia suficiente y SOC final por encima de la reserva. El intervalo de Wilson refleja error de muestreo Monte Carlo, no exactitud de las distribuciones elegidas. La autonomía repite el perfil prescrito hasta la reserva y señala censura a la derecha si alcanza el horizonte. Las transiciones entre ciclos deben ser físicamente compatibles.

Un perfil imposible por potencia no tiene autonomía admisible inferida y devuelve cero. La autonomía equivalente estacionaria se identifica aparte. Las bandas físicas de SOC y energía interpolan avance normalizado, indican cuántas realizaciones llegan a cada punto y no extrapolan después del agotamiento.

### 6.12 Sensibilidad local y global

OAT utiliza cambios locales. Spearman usa rangos en un diseño Latin hypercube. Morris estima efectos elementales sobre una malla de niveles pares y conserva media con signo, media absoluta y dispersión. Su dispersión indica no linealidad e interacciones, no error predictivo.

{{EQ:sobol}}

El diseño Sobol utiliza A y B y una matriz ABi que sustituye la columna i de A por la de B. Los estimadores de primer orden y total se conservan aunque el muestreo finito produzca valores fuera de 0 a 1. Si la respuesta es constante, se informan índices indefinidos. El bootstrap emparejado aproxima error de diseño. Las entradas son uniformes independientes con límites explícitos. No se aplican índices ordinarios a entradas correlacionadas sin cambiar la interpretación.

Los parámetros exploratorios incluyen Crr, CdA, masa, potencia humana, velocidad, viento, temperatura y eficiencia. El resultado depende de los dominios elegidos y de la factibilidad del perfil. Las pruebas contrastan Morris con funciones lineales y Sobol con la referencia Ishigami, incluida la interacción.

```powershell
bikeenergylab sensitivity configs/flat.yaml --method morris --samples 16
bikeenergylab sensitivity configs/flat.yaml --method sobol --samples 256
```

## 7. Restricciones y límites

### 7.1 Identidad de la entrega y límites

{{SOURCE}}

El núcleo fuera de la GUI coincide con el wheel de la revisión científica del 4 de octubre de 2026. Su copia y los expedientes completos están en results/history del espacio de desarrollo, fuera de los ZIP. La distribución contiene el baseline y los registros seleccionados que enumera results/README.md. Los cambios de interfaz no constituyen experimentos nuevos. La verificación actual de artefactos finales está en results/release_verification.json del espacio de desarrollo, fuera de los ZIP. La identidad histórica está en results/release_verification_1.0.0.json, incluido en los paquetes.

La precisión con bicicletas reales, la calibración de probabilidades, los parámetros independientes de hardware y la novedad académica requieren evidencia adicional. El software utiliza dinámica inversa con velocidad prescrita. Los residuos por ruta no identifican una corrección temporal aprendida de SOC, corriente o voltaje.

### 7.2 Protocolos y resultados sintéticos

Entrenamiento, calibración de intervalos y prueba son grupos disjuntos. El protocolo predictivo usa tres semillas 42, 73 y 109. En cada una hay 60 rutas de entrenamiento, 30 de calibración y 15 de prueba por escenario. Se evalúan ID y siete cambios OOD de morfología, pendiente, temperatura, ciclista, masa, viento y combinación. Se conservan comparación de compuertas y ablaciones.

{{TABLE:ID}}

Los valores de la tabla son promedios de las tres semillas en ID. M3 tuvo menor CRPS que M4 en ese protocolo. La cobertura M4 en temperatura y combinación OOD fue cero en las tres semillas: la transferencia de errores aprendidos falló. Estos resultados no sostienen superioridad universal de CGPRA. El intervalo nominal del 95% no debe presentarse como garantía ante cambios de distribución.

El protocolo causal utiliza 32 rutas sintéticas con Crr de 0.008 a 0.011, CdA de 0.48 y ruido de 0.06 Wh/km. Cada predicción se registra antes de consumir el objetivo observado.

{{TABLE:DRIFT}}

En este cambio declarado, M4 adaptativo mejoró al M4 congelado, pero la física adaptativa M1 tuvo el menor MAE. No se generaliza ese resultado a otros cambios ni a telemetría real. Los segmentos no se cuentan como observaciones independientes y tres semillas no justifican una afirmación estadística amplia.

El ZIP distribuido incluye los CSV originales de agregados predictivos y métricas de deriva junto con protocolo y metadatos en results/release-1.0.0/predictive/EXP-20261004-111801-cadfae83 y results/release-1.0.0/prequential/EXP-20261004-111931-387d9cfc. Incluye índices de la suite EXP 01 a 15 y de once ejemplos API. Los expedientes crudos completos permanecen en el espacio de desarrollo y no se incluyen en los ZIP. La GUI 1.0.0 ofrece nueve ejercicios adicionales.

### 7.3 Reproducción y límites de la evidencia

{{SOURCE}}

La ejecución histórica del 6 de octubre registró 80 pruebas de regresión, 114 controles GUI en fuentes y 114 en el EXE. Los logs primarios, el comando de pytest, las versiones y los reportes se incluyen en results/build_logs y results/release-1.0.0/acceptance.json. El inventario de hashes distribuido está en results/evidence-inventory-1.0.0.json. Los hashes de los ZIP finales se conservan por separado en el espacio de desarrollo. El 8 de octubre se volvió a ejecutar la suite completa en Windows con una carpeta temporal aislada. Los protocolos científicos crudos del espacio de desarrollo conservan sus semillas, datos y hashes y no se presentan como nuevos resultados. Las pruebas verifican implementación y distribución, no precisión física.

La revisión de botones utiliza widgets reales y diálogos con respuestas controladas. También comprueba Cargar ejemplo seguido de Simular para los nueve casos. Esta revisión verifica el despacho de los procedimientos, no el aspecto de todos los diálogos de Windows ni todos los estados posibles. Las copias de las tablas históricas en docs/validation_data conservan sus hashes y permiten regenerar este documento desde el código fuente.

Faltan rutas reales independientes, caracterización de batería y motor, validación de probabilidades y evaluación de deriva observada. También se omiten dinámica directa, viento transversal, engranajes y envejecimiento. La originalidad académica necesita revisión sistemática de trabajos previos. Las referencias siguientes sustentan conceptos. No avalan los valores por defecto ni esta implementación particular.

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

Las fuentes, el lock y los scripts permiten repetir el proceso. No se promete igualdad binaria entre builds. La revisión ampliada invoca los botones reales de Tk con respuestas controladas de diálogos, incluyendo archivos, ejemplos, tutorial, modelos, sensibilidad, benchmark, EXP 01 a 15 y exportación. Otra máquina Windows y una revisión de todos los diálogos nativos aportarían evidencia adicional.

La carpeta Entregables contiene únicamente los cuatro DOCX, el ZIP portátil y el ZIP de código fuente. El EXE y sus dependencias están dentro del ZIP portátil. Extraiga el paquete fuera de Entregables y conserve la carpeta BikeEnergyLab completa. Los registros de revisión y hashes de los seis archivos se guardan en results/delivery-1.0.0 del espacio de desarrollo. Ese directorio no forma parte de los ZIP.

## 9. Glosario y referencias académicas

### 9.1 Glosario de términos

| Término | Definición operativa |
| --- | --- |
| Wh y Wh/km | Energía terminal y consumo por distancia |
| SOC | Fracción de carga sobre capacidad efectiva |
| Crr y CdA | Rodadura y área aerodinámica equivalente |
| M1 M2 M3 M4 | Física calibrada, datos, residual fijo y CGPRA |
| Alpha | Peso residual. No probabilidad de acierto |
| ID y OOD | Dominio y cambios de distribución |
| Intervalo conformal | Conjunto calibrado con rutas retenidas |
| Reserva | SOC mínimo para una misión exitosa |
| Censura | Horizonte termina antes del agotamiento |
| Replay | Predicciones de referencia del modelo reconstruido |
| RLS | Actualización secuencial de parámetros |
| ECM | Circuito equivalente de una rama RC |
| SHA256 | Identidad. No firma de autenticidad |


### 9.2 Referencias académicas

La bibliografía se conserva a partir de docs/references.md, donde consta la verificación de objetivos bibliográficos del 1 de octubre de 2026. No se transcriben valores experimentales de esos trabajos como resultados de BikeEnergyLab.

1. Validation of a Mathematical Model for Road Cycling Power. Journal of Applied Biomechanics 14(3), 276 a 291, 1998. Modelo longitudinal de ciclismo. [https://doi.org/10.1123/jab.14.3.276](https://doi.org/10.1123/jab.14.3.276).
2. A simulation and experimental study of dynamic performance and electric consumption of an electric bicycle. Energy Procedia 158, 2865 a 2871, 2019. [https://doi.org/10.1016/j.egypro.2019.01.937](https://doi.org/10.1016/j.egypro.2019.01.937). Se conservan título, revista, año y DOI sin añadir una lista de autores no verificada.
3. Improving the Autonomy of a Mid-Drive Motor Electric Bicycle Based on System Efficiency Maps and Its Performance. World Electric Vehicle Journal 12(2), 59, 2021. [https://www.mdpi.com/2032-6653/12/2/59](https://www.mdpi.com/2032-6653/12/2/59), [https://doi.org/10.3390/wevj12020059](https://doi.org/10.3390/wevj12020059). Mapas de eficiencia. No proporciona coeficientes universales.
4. Bor Yann Liaw, Rudolph G. Jungst, Angel Urbina y Thomas L. Paez. Modeling of Battery Life I. The Equivalent Circuit Model (ECM) Approach. Sandia National Laboratories, EESAT, 2003. [https://www.sandia.gov/ess-ssl/EESAT/2003_papers/Liaw.pdf](https://www.sandia.gov/ess-ssl/EESAT/2003_papers/Liaw.pdf). OCV e impedancia dependen de la química.
5. Physics-guided Neural Networks (PGNN): An Application in Lake Temperature Modeling. 2017. [https://arxiv.org/abs/1710.11431](https://arxiv.org/abs/1710.11431). Contexto de combinación física y datos. Este software utiliza residuos con árboles.
6. Balaji Lakshminarayanan, Alexander Pritzel y Charles Blundell. Simple and Scalable Predictive Uncertainty Estimation using Deep Ensembles. NeurIPS 2017. [https://arxiv.org/abs/1612.01474](https://arxiv.org/abs/1612.01474). La dispersión de árboles no se equipara a un posterior ni a ensembles profundos independientes.
7. Kimin Lee, Kibok Lee, Honglak Lee y Jinwoo Shin. A Simple Unified Framework for Detecting Out-of-Distribution Samples and Adversarial Attacks. NeurIPS 2018. [https://arxiv.org/abs/1807.03888](https://arxiv.org/abs/1807.03888). El soporte Mahalanobis de rutas no reproduce su detector neuronal por clases.
8. A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification. 2021. [https://arxiv.org/abs/2107.07511](https://arxiv.org/abs/2107.07511). La interpretación conformal depende de intercambiabilidad.
9. Max D. Morris. Factorial Sampling Plans for Preliminary Computational Experiments. Technometrics 33(2), 161 a 174, 1991. [https://doi.org/10.1080/00401706.1991.10484804](https://doi.org/10.1080/00401706.1991.10484804).
10. Andrea Saltelli y colaboradores. Variance based sensitivity analysis of model output. Design and estimator for the total sensitivity index. Computer Physics Communications 181(2), 259 a 270, 2010. [https://doi.org/10.1016/j.cpc.2009.09.018](https://doi.org/10.1016/j.cpc.2009.09.018).
