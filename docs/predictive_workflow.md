# Flujo predictivo reproducible — 0.2.0

El modelo híbrido puede guardarse, reconstruirse y utilizarse en API, CLI y GUI.
La propagación opcional de errores de energía observados tiene supuestos explícitos
y no representa una validación real de autonomía o probabilidad de misión.

## Entrenamiento y reutilización

```powershell
bikeenergylab train datasets/synthetic_calibration.csv --seed 42
```

El comando anuncia `results/EXP-.../model`. Este dataset es sintético, sin ruido ni
discrepancia, y sirve para recuperación de parámetros. Para otros datos, proporcionar
rutas independientes con energía terminal observada y sus condiciones conocidas.
`--calibration-dataset` permite declarar un archivo de holdout independiente. Sin
él, una permutación de grupos con semilla reserva 20 rutas y exige al menos 20 para
entrenar. Un intervalo conformal finito 95% requiere al menos 19 grupos reservados.

```powershell
bikeenergylab predict configs/flat.yaml --model "results/EXP-.../model"
bikeenergylab simulate configs/flat.yaml --model "results/EXP-.../model"
bikeenergylab uncertainty configs/flat.yaml --model "results/EXP-.../model"
```

Sustituir `EXP-...` por la ruta anunciada. La CLI reutiliza Crr/CdA calibrados y
conserva las demás condiciones de la solicitud. `predict` exporta M1–M4 con energía
de ruta completa, soporte e intervalos. `simulate` conserva la trayectoria física
y añade la predicción CGPRA de la ruta completa: no confundirla con energía consumida
si la batería agotó la reserva antes de terminar. Los exports incluyen el modelo.
El YAML exportado por incertidumbre referencia un modelo relativo y puede repetirse
desde la CLI después de trasladar toda la carpeta.
Cuando el modelo se obtiene de la referencia del YAML exportado, se conserva la
configuración física completa guardada, incluso un prior explícito distinto del
ajuste. La opción explícita `--model` aplica Crr/CdA del modelo a una solicitud nueva.

En GUI: entrenar o pulsar Abrir modelo CGPRA en Modelo híbrido. Guardar modelo CGPRA
crea un subdirectorio nuevo. Simulación calcula el resultado híbrido en el worker y
lo conserva en el resultado exportable. Cambiar idioma o cargar otro modelo no
recalcula predicciones de resultados anteriores. Misión/autonomía añade muestras
de energía predictiva cuando hay un modelo con errores independientes vigentes.

```python
from bikeenergylab import Config, Route
from bikeenergylab.experiments import generate_observations
from bikeenergylab.residual import CGPRAModel
from bikeenergylab.uncertainty import monte_carlo

train = generate_observations(60, 42, prefix="train")
held = generate_observations(30, 43, prefix="held")
model = CGPRAModel(Config(), seed=42).fit(train)
model.calibrate_intervals(held)
model.save("results/my_model")  # La carpeta debe ser nueva.
restored = CGPRAModel.load("results/my_model")
route = Route.synthetic(3000, 6, grade=0.01, segments=24)
result = monte_carlo(
    model.config, route, n_samples=100, seed=42, hybrid_model=restored,
    distributions={"bike.crr": {
        "distribution": "uniform", "low": 0.006, "high": 0.01,
    }},
)
result.export("results")
```

## Artefacto de modelo

La carpeta contiene manifest.json, training.csv, calibration.csv si existe,
reference_predictions.json y mapas de motor necesarios en assets/. CSV conserva
perfiles temporales, configuración conocida, grupos, pesos y procedencia. El
manifest declara formato, features, semilla, parámetros calibrados, gate,
dependencias, checksums y controles/covarianza secuenciales cuando existen.

Cargar reconstruye Ridge, Random Forest y gate en los parámetros físicos ya
guardados, recalibra errores/intervalos con el holdout y verifica todas las
predicciones de referencia con tolerancia numérica 1e-8. Una diferencia material
se rechaza en lugar de aceptar un modelo distinto. No se ejecuta pickle ni código
incluido en el artefacto. Los checksums detectan modificación accidental; no son
firmas que autentiquen al autor. Las rutas de activos deben quedar dentro de la
carpeta. La reconstrucción no implica ejecutables binariamente idénticos.

`adapt` invalida errores e intervalos. Los grupos de calibración invalidados no
se reutilizan después de observar nuevos datos; se necesitan rutas frescas. El
estado RLS se conserva al guardar para continuar la misma actualización causal.

## Distribución de energía

Para cada baseline, guardar errores independientes con signo por kilómetro:

`e_j = (E_observada_j - E_predicha_j) / distancia_j_km`.

En cada muestra física b, escoger j uniformemente y calcular:

`E_predictiva_b = E_centro_b + distancia_b_km * e_j`.

Los errores no se centran: conservan el sesgo observado. Tampoco se multiplican
por alpha: reducir la corrección residual no elimina el error de la física. Un
flujo aleatorio separado conserva las mismas muestras físicas con/sin aprendizaje.
La componente física usa la configuración efectivamente muestreada; parámetros
calibrados no sustituyen Crr/CdA después del muestreo. En API, el usuario elige
explícitamente la configuración/prior física, normalmente en torno al ajuste.
El Crr global es un parámetro latente calibrado: las features del gate usan la misma
referencia calibrada al entrenar y predecir, conservando contrastes conocidos de
superficie. Cambiar del valor inicial al ajustado no crea por sí mismo un OOD. Los
Crr muestreados sí se conservan en las ecuaciones físicas; no se aprende de este
modo una respuesta residual a su posterior incierto.

Se supone que los errores Wh/km son transferibles y estadísticamente independientes
de las distribuciones de entrada elegidas. No se aprende una distribución conjunta.
El error reservado puede contener incertidumbre de parámetros/mediciones: añadir
priors puede contar parte de ella dos veces. Se exportan scores OOD y fracción fuera
de soporte. Los errores ID no garantizan calibración bajo cambio de condiciones.
Esta distribución empírica se distingue de los conjuntos conformales y carece de
garantía de cobertura finita. La dispersión de árboles sigue siendo un indicador.

Monte Carlo conserva `energy_wh` consumida, `full_route_demand_wh` solicitada,
energía predictiva, corrección, error muestreado, alpha y soporte. La demanda
completa no queda artificialmente limitada por el agotamiento de la batería.

## Presupuesto energético y límites

El screening compara energía predictiva con:

`E_presupuesto = E_nominal * fracción_utilizable * multiplicador_temperatura
                 * (SOC_inicial - SOC_reserva)`.

Solo se identifica para baterías energy/soc con capacidad efectiva constante y
potencia de batería solicitada no negativa en la ruta. Los casos ECM, capacidad
variable y regeneración neta requieren información temporal que el error agregado
no proporciona. No se inventan trayectorias SOC/corriente, alcance híbrido ni
probabilidades de completar dinámicamente la misión.

Las muestras de energía menores que auxiliares, sin regeneración, o menores que
cero en el caso monótono se conservan sin clipping y quedan no identificadas para
esa decisión. Si p es la fracción total de éxitos identificados y u la fracción no
identificada, `[p,p+u]` limita la probabilidad bajo esos supuestos. No es un intervalo
de confianza ni mide error de muestreo. Se entrega un escalar solo cuando u=0.
La suficiencia de potencia de la física base se informa por separado: disponer de
Wh suficientes no identifica fallas transitorias de corriente/voltaje.

`mission_probability`, autonomía por ruta repetida y SOC conservan la simulación
dinámica física. Su intervalo Wilson mide error de muestreo Monte Carlo, no
corrección del modelo ni validez de supuestos.

## Validación ID/OOD

```powershell
bikeenergylab predictive-validation configs/predictive_validation.yaml
```

Tres semillas 42, 73 y 109; 60 rutas de entrenamiento, 30 reservadas y 15 por cada
uno de ocho escenarios. Toda la distribución equiprobable de errores reservados
se usa para CRPS exacto y cuantiles empíricos centrales 95%. No se utilizan bandas
conformales como si fueran una distribución probabilística.

Los presupuestos 0.85, 1.00 y 1.15 veces la energía física calibrada se fijan antes
de consultar etiquetas de test. Brier evalúa si la energía terminal observada es
menor que ese presupuesto. Las tablas de confiabilidad son descriptivas: los tres
presupuestos de una ruta están correlacionados y no son réplicas independientes.
Se retienen todos los datos, modelos, predicciones y métricas por escenario/semilla.
El generador es sintético y declara discrepancia y ruido; sus resultados no
establecen precisión real ni superioridad universal de CGPRA.
