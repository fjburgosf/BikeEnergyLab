# Metodología científica de BikeEnergyLab

## 1. Introducción y alcance

### 1.1 Pregunta de investigación y alcance

La pregunta es si la física calibrada, el aprendizaje residual y una compuerta de confianza pueden mejorar la predicción energética ante nuevas rutas, ciclistas y condiciones. La hipótesis contrastable es que CGPRA mantiene o mejora el error respecto a M1, M2 y M3, especialmente ante cambios de distribución. Los protocolos permiten refutarla. El nombre del método no establece superioridad, novedad ni aceptación académica.

La entrega utiliza datos sintéticos con verdad física y discrepancia declaradas. Los resultados que siguen pertenecen a esos protocolos, no a mediciones de una bicicleta real. La versión 1.0.0 incluye los ejemplos y el tutorial. Su núcleo numérico conserva el comportamiento de la revisión científica histórica del 4 de octubre de 2026. Se conserva la identidad de cada experimento para distinguirlos de las pruebas de software.

## 2. Unidades y convenciones

### 2.1 Unidades y convenciones

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

## 3. Fuerzas y sistema de propulsión

### 3.1 Fuerzas y potencia longitudinal

{{EQ:forces}}

{{EQ:wheel}}

{{EQ:density}}

La forma con signo de la fuerza aerodinámica permite que un viento posterior más rápido que la bicicleta aporte fuerza favorable. Elevar al cuadrado la velocidad relativa sin conservar el signo sería incorrecto. A velocidad cero, la potencia longitudinal es cero; la fricción estática queda fuera del modelo y la fuerza de rodadura se anula en reposo.

Se usa dinámica inversa con velocidad prescrita. El modelo calcula lo necesario para seguir ese perfil y señala demanda no satisfecha cuando los límites lo impiden. No resuelve una trayectoria de velocidad libre. Se omiten viento transversal, inercia rotacional y dinámica del cambio de marchas. El suavizado y la unión de segmentos son aproximaciones; hace falta comprobar convergencia de la segmentación.

### 3.2 Ciclista transmisión y motor

{{EQ:power}}

La masa total reúne bicicleta, ciclista y carga. Crr puede calibrarse para la superficie default o definirse por superficie. Los valores iniciales de rodadura, CdA y transmisión son supuestos, no constantes universales. La contribución humana se limita a la demanda positiva y la potencia sobrante no carga la batería.

La potencia humana admite un valor constante, columnas temporales o un modo condicionado por cadencia, pendiente y fatiga. Los coeficientes iniciales no añaden fatiga ni ganancia por pendiente. Este modo es operativo y no constituye un modelo fisiológico validado.

La asistencia demand ordena una fracción de la demanda; proportional depende del aporte humano multiplicado por la relación de asistencia. Se aplican límites mecánicos, torque equivalente y corte de velocidad configurables. No se supone una normativa territorial. La eficiencia usa una constante o un mapa bilineal en velocidad angular equivalente y torque; se informa si un punto queda fuera de su dominio.

## 4. Batería y balance energético

### 4.1 Batería energética y estado de carga

{{EQ:capacity}}

{{EQ:soc}}

Efull es la capacidad nominal por la fracción usable y un multiplicador térmico empírico, si existe. SOC se define sobre esa base efectiva. Con 500 Wh nominales, fracción 0.95 y SOC de 0.90 a 0.10 hay 380 Wh disponibles. Energy y soc son representaciones equivalentes de esta contabilidad en la versión actual.

La actualización de SOC usa potencia terminal con signo positivo de descarga. Si la temperatura cambia, se usa una aproximación de capacidad efectiva local; no representa retraso térmico ni liberación reversible de capacidad. Sin curvas empíricas no se introduce una pérdida de capacidad por frío. Fuera del dominio de una curva definida se rechaza la extrapolación.

### 4.2 Circuito equivalente de batería

{{EQ:ecm}}

El ECM Thevenin de una rama RC resuelve potencia terminal P igual a V por I mediante la raíz de corriente pequeña estable. Limita corriente de descarga, corriente de carga y voltaje. La carga se integra con capacidad efectiva en Ah y la rama RC se actualiza exactamente para corriente constante en cada subpaso.

La energía terminal y la potencia química OCV por I son distintas y se exportan por separado. Ah requiere caracterización propia; cambiar Wh no modifica automáticamente la capacidad de conteo de carga. OCV, R0, R1 y C1 iniciales son ilustrativos. El voltaje se evalúa al inicio del subpaso; reducir dt y comprobar convergencia es necesario. No se modelan envejecimiento, electroquímica detallada ni temperatura interna.

### 4.3 Límites regeneración y balance

La batería detiene o acorta el subpaso al alcanzar el límite de energía o SOC. La regeneración está desactivada por defecto. Activarla requiere hardware capaz, frenado o descenso, velocidad mínima, límite eléctrico y margen de corriente y SOC para cargar. Los auxiliares pueden consumir potencia regenerada incluso con la batería llena.

{{EQ:terminal}}

El balance completo suma contribuciones mecánicas con signo, pérdidas de transmisión y motor, conversión regenerativa, disipación de frenado, auxiliares y demanda no satisfecha. energy_balance_error_w comprueba la identidad implementada. La recuperación se informa aparte; no debe restarse de nuevo a la energía de pendiente, porque duplicaría el efecto del descenso.

## 5. Calibración y aprendizaje residual

### 5.1 Calibración e identificabilidad

{{EQ:fit}}

El ajuste usa least_squares acotado y rutas completas con pesos wi. Los parámetros por defecto son Crr y CdA. Ajustar eficiencia, potencia humana o auxiliares requiere límites y excitación independiente suficientes. Las condiciones de cada observación se conservan y solo se transfieren los parámetros ajustados.

La identificabilidad práctica se examina con Jacobiano normalizado por amplitud de parámetros, rango SVD, condición y coseno entre columnas. Parámetros en fronteras, sensibilidades colineales o rango insuficiente deben informarse. Un residuo pequeño no demuestra identificación física. La covarianza local aproximada no constituye un posterior calibrado bajo deficiencia de rango o pérdidas robustas.

El experimento de recuperación utiliza cero discrepancia y cero ruido. El benchmark también introduce discrepancia estructural: los parámetros físicos pueden absorber sesgo residual. Deben analizarse errores y diagnósticos junto con los valores de parámetros.

### 5.2 Aprendizaje residual y modelos comparados

{{EQ:residual}}

{{EQ:models}}

r es el residuo en Wh/km y L la distancia en km, de modo que la corrección final queda en Wh. M2 usa Ridge escalado y el aprendizaje residual usa Random Forest con semilla. No se presupone que una arquitectura profunda mejore este problema.

Las características incluyen medias temporales de velocidad, velocidad cúbica, aceleración, pendiente con signo y positiva, viento, temperatura, potencia humana, masa, asistencia, Crr y variación de velocidad. Estos resúmenes descartan parte de la secuencia de la ruta. Un piso numérico de escala 1e-6 evita que redondeo en columnas casi constantes produzca soporte OOD artificialmente extremo; no representa precisión de sensor.

### 5.3 Compuerta de confianza y soporte OOD

{{EQ:gate}}

La compuerta simple normaliza distancias kNN mediante el percentil 95 de distancias de entrenamiento dejando fuera el punto propio. La avanzada usa el mayor soporte normalizado entre kNN y Mahalanobis con covarianza regularizada, y penaliza dispersión de árboles. n es el número de rutas de entrenamiento, d el soporte normalizado y u la dispersión normalizada por la desviación de residuos de entrenamiento. La simple usa u igual a cero.

Los coeficientes se fijan antes de probar. La dispersión de árboles es heurística y no una desviación bayesiana. Alpha es un peso residual, no una probabilidad de acierto. Un alpha pequeño devuelve la predicción hacia la física calibrada, que también puede tener sesgo. La distancia OOD no detecta todos los cambios condicionales.

## 6. Incertidumbre misión y sensibilidad

### 6.1 Intervalos y propagación de incertidumbre

{{EQ:conformal}}

La calibración conformal usa grupos independientes y errores absolutos en Wh/km. El rango del cuantil k usa n rutas de calibración y cobertura c; para 95% se necesitan al menos 19 rutas. Cada modelo usa sus propios errores retenidos. Las garantías finitas requieren intercambiabilidad, por lo que la cobertura OOD se mide y no se garantiza.

Monte Carlo muestrea distribuciones físicas configuradas, normales truncadas o uniformes, y admite una distribución gaussiana conjunta acotada. La covarianza local de calibración, si se utiliza, conserva su carácter aproximado. Se pueden propagar errores de elevación con el filtro mediano registrado. Los perfiles temporales tienen prioridad; se rechaza incertidumbre escalar que no pudiera afectar al perfil.

Los errores firmados retenidos CGPRA pueden añadirse a la demanda de ruta completa como un análisis predictivo separado. Ese muestreo necesita calibración vigente y supuestos de transferencia de error. El presupuesto energético no identifica una corrección dinámica de SOC, voltaje o corriente. Un conjunto conformal por sí solo no define una distribución para calcular CRPS.

### 6.2 Misión autonomía y trayectorias

{{EQ:mission}}

El éxito requiere ruta completa, potencia suficiente y SOC final por encima de la reserva. El intervalo de Wilson refleja error de muestreo Monte Carlo, no exactitud de las distribuciones elegidas. La autonomía repite el perfil prescrito hasta la reserva y señala censura a la derecha si alcanza el horizonte. Las transiciones entre ciclos deben ser físicamente compatibles.

Un perfil imposible por potencia no tiene autonomía admisible inferida y devuelve cero. La autonomía equivalente estacionaria se identifica aparte. Las bandas físicas de SOC y energía interpolan avance normalizado, indican cuántas realizaciones llegan a cada punto y no extrapolan después del agotamiento.

### 6.3 Sensibilidad local y global

OAT utiliza cambios locales; Spearman usa rangos en un diseño Latin hypercube. Morris estima efectos elementales sobre una malla de niveles pares y conserva media con signo, media absoluta y dispersión. Su dispersión indica no linealidad e interacciones, no error predictivo.

{{EQ:sobol}}

El diseño Sobol utiliza A y B y una matriz ABi que sustituye la columna i de A por la de B. Los estimadores de primer orden y total se conservan aunque el muestreo finito produzca valores fuera de 0 a 1. Si la respuesta es constante, se informan índices indefinidos. El bootstrap emparejado aproxima error de diseño. Las entradas son uniformes independientes con límites explícitos; no se aplican índices ordinarios a entradas correlacionadas sin cambiar la interpretación.

Los parámetros exploratorios incluyen Crr, CdA, masa, potencia humana, velocidad, viento, temperatura y eficiencia. El resultado depende de los dominios elegidos y de la factibilidad del perfil. Las pruebas contrastan Morris con funciones lineales y Sobol con la referencia Ishigami, incluida la interacción.

## 7. Protocolos y resultados

### 7.1 Protocolos y resultados sintéticos

Entrenamiento, calibración de intervalos y prueba son grupos disjuntos. El protocolo predictivo usa tres semillas 42, 73 y 109; en cada una hay 60 rutas de entrenamiento, 30 de calibración y 15 de prueba por escenario. Se evalúan ID y siete cambios OOD de morfología, pendiente, temperatura, ciclista, masa, viento y combinación. Se conservan comparación de compuertas y ablaciones.

{{TABLE:ID}}

Los valores de la tabla son promedios de las tres semillas en ID. M3 tuvo menor CRPS que M4 en ese protocolo. La cobertura M4 en temperatura y combinación OOD fue cero en las tres semillas: la transferencia de errores aprendidos falló. Estos resultados no sostienen superioridad universal de CGPRA. El intervalo nominal del 95% no debe presentarse como garantía ante cambios de distribución.

El protocolo causal utiliza 32 rutas sintéticas con Crr de 0.008 a 0.011, CdA de 0.48 y ruido de 0.06 Wh/km. Cada predicción se registra antes de consumir el objetivo observado.

{{TABLE:DRIFT}}

En este cambio declarado, M4 adaptativo mejoró al M4 congelado, pero la física adaptativa M1 tuvo el menor MAE. No se generaliza ese resultado a otros cambios ni a telemetría real. Los segmentos no se cuentan como observaciones independientes y tres semillas no justifican una afirmación estadística amplia.

Las rutas de evidencia son results/release-1.0.0/predictive/EXP-20261004-111801-cadfae83 y results/release-1.0.0/prequential/EXP-20261004-111931-387d9cfc. La suite EXP 01 a 15 y los once ejemplos API ejecutados se conservan bajo release-1.0.0 con sus metadatos. La GUI 1.0.0 ofrece nueve ejercicios de aprendizaje adicionales como catálogo integrado.

## 8. Reproducción y límites

### 8.1 Reproducción y límites de la evidencia

{{SOURCE}}

La versión 1.0.0 pasó 80 pruebas de regresión y verificaciones de GUI, wheel aislado y ejecutable. Esa evidencia comprueba implementación y distribución; no reemplaza validación de precisión física. Cada ejecución conserva configuración, semillas, datos, versiones y hashes. Deben conservarse los resultados desfavorables y la identidad de sus fuentes.

La revisión de botones utiliza widgets reales y diálogos con respuestas controladas; también comprueba Cargar ejemplo seguido de Simular para los nueve casos. Esta revisión verifica el despacho de los procedimientos, no el aspecto de todos los diálogos de Windows ni todos los estados posibles. Las copias de las tablas históricas en docs/validation_data conservan sus hashes y permiten regenerar este documento desde el código fuente.

Faltan rutas reales independientes, caracterización de batería y motor, validación de probabilidades y evaluación de deriva observada. También se omiten dinámica directa, viento transversal, engranajes y envejecimiento. La originalidad académica necesita revisión sistemática de trabajos previos. Las referencias siguientes sustentan conceptos; no avalan los valores por defecto ni esta implementación particular.

## 9. Referencias académicas

### 9.1 Referencias académicas

La bibliografía se conserva a partir de docs/references.md, donde consta la verificación de objetivos bibliográficos del 1 de octubre de 2026. No se transcriben valores experimentales de esos trabajos como resultados de BikeEnergyLab.

1. Validation of a Mathematical Model for Road Cycling Power. Journal of Applied Biomechanics 14(3), 276 a 291, 1998. Modelo longitudinal de ciclismo. [DOI del editor](https://doi.org/10.1123/jab.14.3.276).
2. A simulation and experimental study of dynamic performance and electric consumption of an electric bicycle. Energy Procedia 158, 2865 a 2871, 2019. [DOI del editor](https://doi.org/10.1016/j.egypro.2019.01.937). Se conservan título, revista, año y DOI sin añadir una lista de autores no verificada.
3. Improving the Autonomy of a Mid-Drive Motor Electric Bicycle Based on System Efficiency Maps and Its Performance. World Electric Vehicle Journal 12(2), 59, 2021. [Artículo del editor](https://www.mdpi.com/2032-6653/12/2/59), [DOI](https://doi.org/10.3390/wevj12020059). Mapas de eficiencia; no proporciona coeficientes universales.
4. Bor Yann Liaw, Rudolph G. Jungst, Angel Urbina y Thomas L. Paez. Modeling of Battery Life I. The Equivalent Circuit Model (ECM) Approach. Sandia National Laboratories, EESAT, 2003. [Documento primario](https://www.sandia.gov/ess-ssl/EESAT/2003_papers/Liaw.pdf). OCV e impedancia dependen de la química.
5. Physics-guided Neural Networks (PGNN): An Application in Lake Temperature Modeling. 2017. [Documento de autores](https://arxiv.org/abs/1710.11431). Contexto de combinación física y datos; este software utiliza residuos con árboles.
6. Balaji Lakshminarayanan, Alexander Pritzel y Charles Blundell. Simple and Scalable Predictive Uncertainty Estimation using Deep Ensembles. NeurIPS 2017. [Documento de autores](https://arxiv.org/abs/1612.01474). La dispersión de árboles no se equipara a un posterior ni a ensembles profundos independientes.
7. Kimin Lee, Kibok Lee, Honglak Lee y Jinwoo Shin. A Simple Unified Framework for Detecting Out-of-Distribution Samples and Adversarial Attacks. NeurIPS 2018. [Documento de autores](https://arxiv.org/abs/1807.03888). El soporte Mahalanobis de rutas no reproduce su detector neuronal por clases.
8. A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification. 2021. [Tutorial de autores](https://arxiv.org/abs/2107.07511). La interpretación conformal depende de intercambiabilidad.
9. Max D. Morris. Factorial Sampling Plans for Preliminary Computational Experiments. Technometrics 33(2), 161 a 174, 1991. [DOI del editor](https://doi.org/10.1080/00401706.1991.10484804).
10. Andrea Saltelli y colaboradores. Variance based sensitivity analysis of model output. Design and estimator for the total sensitivity index. Computer Physics Communications 181(2), 259 a 270, 2010. [DOI del editor](https://doi.org/10.1016/j.cpc.2009.09.018).

